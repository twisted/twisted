#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
# 
from twisted.web.resource import Resource
from twisted.internet import defer
from twisted.web.error import Error, ErrorPage
import md5, time, random
    
def digestPassword(username, realm, password):
    return md5.md5("%s:%s:%s" % (username,realm,password)).hexdigest()

class DigestAuthenticator:
    """ Simple implementation of RFC 2617 - HTTP Digest Authentication """
    def __init__(self, realm, userfunc):
        """
            realm is a globally unique URI, like tag:clarkevans.com,2004:bing
            userfunc(realm, username) -> MD5('%s:%s:%s') % (user,realm,pass)
        """
        self.nonce    = {} # list to prevent replay attacks
        self.userfunc = userfunc
        self.realm    = realm

    def requestAuthentication(self, request, stale = ''):
        nonce  = md5.md5("%s:%s" % (time.time(),random.random())).hexdigest()
        opaque = md5.md5("%s:%s" % (time.time(),random.random())).hexdigest()
        if stale: stale = 'stale="true", '
        request.setHeader("WWW-Authenticate",('Digest realm="%s", qop="auth"'
         ', nonce="%s", opaque="%s"%s') % (self.realm,nonce,opaque,stale))
        self.nonce[nonce] = 0
        request.setResponseCode(401)

    def compute(self, request, ha1, method, uri, nonce, nc, 
                cnonce, qop, response):
        if not ha1:
            self.requestAuthentication(request)
            return
        ha2 = md5.md5('%s:%s' % (method,uri)).hexdigest()
        if qop:
            chk = "%s:%s:%s:%s:%s:%s" % (ha1,nonce,nc,cnonce,qop,ha2)
        else:
            chk = "%s:%s:%s" % (ha1,nonce,ha2)
        if response != md5.md5(chk).hexdigest():
            if nonce in self.nonce:
                del self.nonce[nonce]
            self.requestAuthentication(request)
            return
        if nc <= self.nonce.get(nonce,'00000000'):
            if nonce in self.nonce:
                del self.nonce[nonce]
            self.requestAuthentication(request, stale = True)
            return
        self.nonce[nonce] = nc
        return True
    
    def authenticate(self, request):
        method = request.method
        auth = request.getHeader('Authorization')
        if not auth:
            self.requestAuthentication(request)
            return defer.succeed(False)
        (authtype, auth) = auth.split(" ", 1)
        if 'Digest' != authtype:
            raise Error(400,"unknown authorization type")
        amap = {}
        for itm in auth.split(", "):
            (k,v) = [s.strip() for s in itm.split("=",1)]
            amap[k] = v.replace('"','')
        try:
            username = amap['username']
            uri      = amap['uri']
            nonce    = amap['nonce']
            realm    = amap['realm']
            response = amap['response']
            assert uri == request.uri
            assert realm == self.realm
            qop      = amap.get('qop','')
            cnonce   = amap.get('cnonce','')
            nc       = amap.get('nc','00000000')
            if qop:
                assert 'auth' == qop
                assert nonce and nc
        except:
            raise Error(400,"malformed credentials")
        d = defer.maybeDeferred(self.userfunc,realm,username)
        d.addCallback(lambda ha1: self.compute(request,ha1,method,uri,
                                      nonce,nc,cnonce,qop,response))
        return d
    
    __call__ = authenticate

class DigestResource(Resource):
    def __init__(self, realm, userfunc, authpage = None):
        Resource.__init__(self)
        self.__authenticate = DigestAuthenticator(realm, userfunc)
        self.__authpage = authpage or \
            ErrorPage(401,'Authentication Required',
              "This server could not verify that you "
              "are authorized to access the document you "
              "requested.  Either you supplied the wrong "
              "credentials (e.g., bad password), or your "
              "browser doesn't understand how to supply "
              "the credentials required.")

    def getChildWithDefault(self,path,request):
        d = self.__authenticate(request)
        assert d.called, "digest resource doesn't work with deferreds"
        if d.result:
            return Resource.getChildWithDefault(self,path,request)
        else:
            return self.__authpage

def test():
    from twisted.internet import reactor
    from twisted.web.server import Site
    from twisted.web.static import Data
    realm = "tag:clarkevans.com,2002:testing"
    data  = Data("<html><body>protected resource</body></head>","text/html")
    def gethash(realm,username):
        """ dummy password hash, where user password is just reverse """
        password = list(username)
        password.reverse()
        password = "".join(password)
        return digestPassword(username,realm,password)
    root = DigestResource(realm, gethash)
    root.putChild("data",data)
    site = Site(root)
    reactor.listenTCP(8080,site)
    reactor.run()

if '__main__' == __name__:
    import sys               
    from twisted.python import log 
    log.startLogging(sys.stdout, 0) 
    test()

#
# You can use urllib2 to test this module, but Digest Authentication is
# broken up till urllib2.py revision 1.53.6.2 or Python 2.3.4; so, if
# you have Python 2.3.2 or 2.3.3 you can fetch this file from CVS.
#
# curl --user bing:gnib --digest "http://127.0.0.1:8080/data"
#
def fetch():
    import urllib2
    uri = "http://127.0.0.1:8080/"
    auth = urllib2.HTTPDigestAuthHandler()
    auth.add_password('tag:clarkevans.com,2002:testing',uri,'bing','gnib')
    opener = urllib2.build_opener(auth)
    print opener.open(uri + "data").read()
    try:
        print opener.open(uri + "bad").read()
    except Exception, e:
        assert e.code == 404, "file not found"
    print opener.open(uri + "data").read()
