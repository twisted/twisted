# -*- test-case-name: twisted.test.test_woven -*-
# Resource protection for Woven.

import random
import time
import md5

# Twisted Imports

from twisted.python import log, components
from twisted.web.resource import Resource
from twisted.web.util import redirectTo, Redirect
from twisted.internet import reactor

def _sessionCookie():
    return md5.new("%s_%s" % (str(random.random()) , str(time.time()))).hexdigest()

class GuardSession(components.Componentized):
    """A user's session with a system.

    This utility class contains no functionality, but is used to
    represent a session.
    """
    def __init__(self, guard, uid):
        """Initialize a session with a unique ID for that session.
        """
        components.Componentized.__init__(self)
        self.guard = guard
        self.uid = uid
        self.expireCallbacks = []
        self.setLifetime(60)
        self.touch()

    def _getSelf(self, interface=None):
        self.touch()
        if interface is None:
            return self
        else:
            return self.getComponent(interface)

    def setLifetime(self, lifetime):
        """Set the approximate lifetime of this session, in seconds.

        This is highly imprecise, but it allows you to set some general
        parameters about when this session will expire.  A callback will be
        scheduled each 'lifetime' seconds, and if I have not been 'touch()'ed
        in half a lifetime, I will be immediately expired.
        """
        self.lifetime = lifetime

    def notifyOnExpire(self, callback):
        """Call this callback when the session expires or logs out.
        """
        self.expireCallbacks.append(callback)

    def expire(self):
        """Expire/logout of the session.
        """
        log.msg("expired session %s" % self.uid)
        del self.guard.sessions[self.uid]
        for c in self.expireCallbacks:
            try:
                c()
            except:
                log.err()
        self.expireCallbacks = []

    def touch(self):
        self.lastModified = time.time()

    def checkExpired(self):
        # If I haven't been touched in 15 minutes:
        if time.time() - self.lastModified > self.lifetime / 2:
            if self.site.sessions.has_key(self.uid):
                self.expire()
            else:
                log.msg("no session to expire: %s" % self.uid)
        else:
            log.msg("session given the will to live for %s more seconds" % self.lifetime)
            reactor.callLater(self.lifetime, self.checkExpired)

INIT_SESSION = 'session-init'

def _setSession(wrap, req, cook):
    req.session = wrap.sessions[cook]
    req.getSession = req.session._getSelf

class SessionWrapper(Resource):

    def __init__(self, rsrc):
        Resource.__init__(self)
        self.resource = rsrc
        self.cookieKey = "woven_session_" + _sessionCookie()
        self.sessions = {}

    def getChild(self, path, request):
        # we need this in several cases, so let's get it here:
        if not request.prepath:
            return None
        pp = request.prepath.pop()
        _urlToMe = request.prePathURL()
        def urlToChild(*ar):
            c = '/'.join(ar)
            if _urlToMe[-1] == '/':
                # this SHOULD only happen in the case where the URL is just the hostname
                return _urlToMe + c
            else:
                return _urlToMe + '/' + c
        request.prepath.append(pp)
        # print "I think I'm at:", _urlToMe
        cookie = request.getCookie(self.cookieKey)
        setupURL = request.setupSessionURL = urlToChild(INIT_SESSION, *([path]+request.postpath))
        request.setupSession = lambda: Redirect(setupURL)
        if self.sessions.has_key(path):
            self.sessions[path].setLifetime(1800)
            if cookie == path:
                # /sessionized-url/aef9c34aecc3d9148/foo
                #                  ^
                #                  we are this getChild
                # with a matching cookie
                rd = Redirect(urlToChild(*request.postpath))
                rd.isLeaf = 1
                return rd
            else:
                # We attempted to negotiate the session but failed (the user
                # probably has cookies disabled): now we're going to return the
                # resource we contain.  In general the getChild shouldn't stop
                # there.
                # /sessionized-url/aef9c34aecc3d9148/foo
                #                 ^ we are this getChild
                # without a cookie (or with a mismatched cookie)
                _setSession(self, request, path)
                return self.resource
        elif self.sessions.has_key(cookie):
            # /sessionized-url/foo
            #                 ^ we are this getChild
            # with a session
            _setSession(self, request, cookie)
            return self.resource.getChildWithDefault(path, request)
        elif path == INIT_SESSION:
            # initialize the session
            # /sessionized-url/session-init
            #                  ^ this getChild
            # without a session
            newCookie = _sessionCookie()
            request.addCookie(self.cookieKey, newCookie, path="/")
            rd = Redirect(urlToChild(newCookie,*request.postpath))
            rd.isLeaf = 1
            sz = self.sessions[newCookie] = GuardSession(self,newCookie)
            sz.checkExpired()
            return rd
        else:
            # /sessionized-url/foo
            #                 ^ we are this getChild
            # without a session
            request.getSession = lambda interface=None: None
            return self.resource.getChildWithDefault(path, request)
