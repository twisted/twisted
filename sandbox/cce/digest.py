#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
# 
from twisted.web.resource import Resource
from twisted.web.error import ErrorPage
import md5, time, random

class DigestAuthentication(Resource):
    """ Simple implementation of RFC 2617 - HTTP Digest Authentication """
    def __init__(self, realm, userfunc, authpage = None, 
                 failpage = None, testall = True):
        """
            parent is the page that the getChild request is forwarded to
            realm is a globally unique URI, like tag:clarkevans.com,2004:bing
            authpage is body to show user when authorization is needed
            failpage is body to show to user when authorization failed
            userfunc(realm, username) -> MD5('%s:%s:%s') % (user,realm,pass)
        """
        Resource.__init__(self)
        self.__nonce    = {} # list to prevent replay attacks
        self.__userfunc = userfunc
        self.__realm    = realm
        self.__testall  = testall
        self.__authpage = authpage or \
            ErrorPage(401,'Authentication Required',
              "This server could not verify that you "
              "are authorized to access the document you "
              "requested.  Either you supplied the wrong "
              "credentials (e.g., bad password), or your "
              "browser doesn't understand how to supply "
              "the credentials required.")
        self.__failpage  = failpage  or \
            ErrorPage(400,'Bad Authentication','Bad Authentication')

    def sendAuthenticateResponse(self, request, stale = ''):
        nonce = md5.md5(str(time.time() + random.random())).hexdigest()
        opaque = md5.md5(str(time.time() + random.random())).hexdigest()
        if stale: stale = 'stale="true", '
        request.setHeader("WWW-Authenticate",('Digest realm="%s", qop="auth"'
         ', nonce="%s", opaque="%s"%s') % (self.__realm,nonce,opaque,stale))
        self.__nonce[nonce] = 0
        request.setResponseCode(401)
        return self.__authpage
           
    def testAuthentication(self, request):
        method = request.method
        auth = request.getHeader('Authorization')
        if not auth:
            return self.sendAuthenticateResponse(request)
        (authtype, auth) = auth.split(" ", 1)
        print auth
        if 'Digest' != authtype:
            return self.__failpage
        amap = {}
        for itm in auth.split(", "):
            (k,v) = [s.strip() for s in itm.split("=",1)]
            amap[k] = v.replace('"','')
        try:
            username = amap['username']
            uri      = amap['uri']
            nonce    = amap['nonce']
            realm    = amap['realm']
            assert uri == request.uri
            assert realm == self.__realm
            qop      = amap.get('qop','')
            cnonce   = amap.get('cnonce','')
            nc       = amap.get('nc','00000000')
            if qop:
                assert 'auth' == qop
                assert nonce and nc
        except:
            return self.__failpage
        ha1 = self.__userfunc(realm,username)
        if not ha1:
            return self.sendAuthenticateResponse(request)
        ha2 = md5.md5('%s:%s' % (method,uri)).hexdigest()
        if qop:
            chk = "%s:%s:%s:%s:%s:%s" % (ha1,nonce,nc,cnonce,qop,ha2)
        else:
            chk = "%s:%s:%s" % (ha1,nonce,ha2)
        if amap['response'] != md5.md5(chk).hexdigest():
            if nonce in self.__nonce:
                del self.__nonce[nonce]
            return self.sendAuthenticateResponse(request)
        if nc <= self.__nonce.get(nonce,'00000000'):
            if nonce in self.__nonce:
                del self.__nonce[nonce]
            return self.sendAuthenticateResponse(request,stale=True)
        self.__nonce[nonce] = nc
        return None # all is well

    def getChildWithDefault(self,path,request):
        if self.__testall:
            epage = self.testAuthentication(request)
            if epage: 
                return epage
        return Resource.getChildWithDefault(self,path,request)

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
        return md5.md5("%s:%s:%s" % (username,realm,password)).hexdigest()
    root = DigestAuthentication(realm, gethash)
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
# broken up till urllib2.py revision 1.53.6.2 ; so, if you have Python
# 2.3.2 you can fetch the following URL and just overwrite urllib2.py
# http://cvs.sf.net/viewcvs.py/*checkout*/python/python/dist/src/Lib/urllib2.py?rev=1.53.6.2
#
# also works with curl,
#
# curl --user bing:gnib --digest "http://127.0.0.1:8080/data"
#
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

