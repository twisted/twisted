#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
# 
from twisted.web.resource import Resource
from twisted.web.error import ErrorPage
import md5, time, random

class DigestAuthentication(Resource):
    """ Simple implementation of RFC 2617 - HTTP Digest Authentication """
    def __init__(self, realm, userfunc, authpage = None, errpage = None):
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
        self.__authpage = authpage or \
            ErrorPage(401,'Authentication Required','Please Authenticate')
        self.__errpage  = errpage  or \
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
           
    def testAuthorization(self, request):
        method = request.method
        auth = request.getHeader('Authorization')
        if not auth:
            return self.sendAuthenticateResponse(request)
        (authtype, auth) = auth.split(" ", 1)
        if 'Digest' != authtype:
            return self._errpage
        amap = {}
        for itm in auth.split(", "):
            (k,v) = [s.strip() for s in itm.split("=",1)]
            amap[k] = v.replace('"','')
        try:
            username = amap['username']
            nonce    = amap['nonce']
            seqno    = amap['nc']
            uri      = amap['uri']
            cnonce   = amap['cnonce']
            assert uri == request.uri
        except:
            return self._errpage
        ha1 = self.__userfunc(self.__realm,username)
        if not ha1:
            return self.sendAuthenticateResponse(request)
        ha2 = md5.md5('%s:%s' % (method,uri)).hexdigest()
        chk = "%s:%s:%s:%s:%s:%s" % (ha1,nonce,seqno,cnonce,'auth',ha2)
        if amap['response'] != md5.md5(chk).hexdigest():
            if nonce in self.__nonce:
                del self.__nonce[nonce]
            return self.sendAuthenticateResponse(request)
        if seqno <= self.__nonce.get(nonce,'00000000'):
            if nonce in self.__nonce:
                del self.__nonce[nonce]
            return self.sendAuthenticateResponse(request,stale=True)
        self.__nonce[nonce] = seqno
        return None # all is well

    def getChildWithDefault(self,path,request):
        epage = self.testAuthorization(request)
        if epage: return epage
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

