import base64
import urllib, urllib2
import md5, sha
import time

from zope.interface import implements, Interface

class IHTTPAuthHandler(Interface):
    def getCredentials(challenge, request=None):
        """Get credentials to handle challenge,
        optional request argument necessary for Digest auth
        """
        pass

    def defaultCredentials(username, password):
        pass
    
    def addCredentials(realm, username, password):
        pass

    def encodeCredentials(creds, challenge, request=None):
        """
        called by getCredentials to handle scheme specific
        generation of credentials
        """
        pass

class HTTPAuthError(Exception):
    pass

class BaseHTTPAuthHandler:
    implements(IHTTPAuthHandler)
    scheme = None
    
    def __init__(self, credentials=None):
        self.credentials = credentials or {}

    def addCredentials(self, realm, username, password):
        self.credentials[realm] = (username, password)

    def getCredentials(self, challenge, request=None):
        if not 'realm' in challenge:
            raise HTTPAuthError("No realm in challenge")

        elif challenge['realm'] not in self.credentials:
            raise HTTPAuthError("No credentials for realm: %s" % challenge['realm'])
        
        return [self.scheme, self.encodeCredentials(self.credentials[challenge['realm']], challenge, request)]
    
    def encodeCredentials(self, creds, challenge, request=None):
        raise NotImplemented("Implemented by subclass")

class HTTPBasicAuthHandler(BaseHTTPAuthHandler):
    scheme = 'Basic'
    
    def encodeCredentials(self, creds, challenge, request=None):
        return base64.encodestring(':'.join(creds).strip(''))


class HTTPDigestAuthHandler(BaseHTTPAuthHandler):
    scheme = 'Digest'
    
    def __init__(self, credentials=None):
        self.credentials = credentials or {}
        self.nonce_counts = {}
        
    def encodeCredentials(self, creds, challenge, request=None):
        dr = {} # response dictionary
        
        try:
            dr['realm'] = challenge['realm']
            dr['nonce'] = challenge['nonce']
            qop = challenge.get('qop')
            dr['algorithm'] = challenge.get('algorithm', 'MD5')
            opaque = challenge.get('opaque') # apparently some implementations don't send this
        except KeyError:
            return None

        H, KD = self._getAlgorithm(dr['algorithm'])
        if H is None:
            return None

        dr['username'], pw = creds
        A1 = ':'.join((dr['username'], dr['realm'], pw))

        dr['uri'] = '?'.join((request.path, urllib.urlencode(request.args)))

        A2 = ':'.join((request.method, dr['uri']))
        
        if qop == 'auth':
            dr['qop'] = qop
            #I think this is a true nonce count unlike urllib2's class nonce_count
            if dr['nonce'] not in self.nonce_counts:
                self.nonce_counts[dr['nonce']] = 0

            self.nonce_counts[dr['nonce']] += 1
            
            dr['nc'] = "%08x" % self.nonce_counts[dr['nonce']]
            dr['cnonce'] = self._getCnonce(dr['nonce'])
            noncebit = "%s:%s:%s:%s:%s" % (dr['nonce'], dr['nc'], dr['cnonce'],
                                           dr['qop'], H(A2))
            
            dr['response'] = KD(H(A1), noncebit)
        elif qop is None:
            dr['response'] = KD(H(A1), "%s:%s" % (dr['nonce'], H(A2)))

        if opaque:
            dr['opaque'] = opaque
            
        return dr

    def _getCnonce(self, nonce):
        # from urllib2
        # The cnonce-value is an opaque
        # quoted string value provided by the client and used by both client
        # and server to avoid chosen plaintext attacks, to provide mutual
        # authentication, and to provide some message integrity protection.
        # This isn't a fabulous effort, but it's probably Good Enough.
        dig = sha.new("%s:%s:%s:%s" % (self.nonce_counts[nonce], nonce, time.ctime(),
                                       urllib2.randombytes(8))).hexdigest()
        return dig[:16]
                
    def _getAlgorithm(self, algo):
        H = None
        if algo == 'MD5':
            H = lambda x: md5.new(x).hexdigest()
        elif algo == 'SHA':
            H = lambda x: sha.new(x).hexdigest()

        KD = lambda s, d: H("%s:%s" % (s, d))
        return H, KD
        


