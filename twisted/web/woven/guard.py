# -*- test-case-name: twisted.test.test_woven -*-
# Resource protection for Woven.

from __future__ import nested_scopes

__version__ = "$Revision: 1.18 $"[11:-2]

import random
import time
import md5

# Twisted Imports

from twisted.python import log, components
from twisted.web.resource import Resource, IResource
from twisted.web.util import redirectTo, Redirect
from twisted.web.static import addSlash
from twisted.internet import reactor
from twisted.cred.error import Unauthorized, LoginFailed, UnauthorizedLogin

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
        self.checkExpiredID = None
        self.setLifetime(60)
        self.services = {}
        self.portals = {}
        self.touch()

    def _getSelf(self, interface=None):
        self.touch()
        if interface is None:
            return self
        else:
            return self.getComponent(interface)

    # Old Guard interfaces

    def clientForService(self, service):
        x = self.services.get(service)
        if x:
            return x[1]
        else:
            return x

    def setClientForService(self, ident, perspective, client, service):
        if self.services.has_key(service):
            p, c, i = self.services[service]
            p.detached(c, ident)
            del self.services[service]
        else:
            self.services[service] = perspective, client, ident
            perspective.attached(client, ident)
        # this return value is useful for services that need to do asynchronous
        # stuff.
        return client

    # New Guard Interfaces

    def resourceForPortal(self, port):
        return self.portals.get(port)

    def setResourceForPortal(self, rsrc, port, logout):
        self.portalLogout(port)
        self.portals[port] = rsrc, logout
        return rsrc

    def portalLogout(self, port):
        p = self.portals.get(port)
        if p:
            r, l = p
            try: l()
            except: log.err()
            del self.portals[port]

    # timeouts and expiration

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
        if self.checkExpiredID:
            self.checkExpiredID.cancel()
            self.checkExpiredID = None

    def touch(self):
        self.lastModified = time.time()

    def checkExpired(self):
        self.checkExpiredID = None
        # If I haven't been touched in 15 minutes:
        if time.time() - self.lastModified > self.lifetime / 2:
            if self.guard.sessions.has_key(self.uid):
                self.expire()
            else:
                log.msg("no session to expire: %s" % self.uid)
        else:
            log.msg("session given the will to live for %s more seconds" % self.lifetime)
            self.checkExpiredID = reactor.callLater(self.lifetime,
                                                    self.checkExpired)
    def __getstate__(self):
        d = self.__dict__.copy()
        if d.has_key('checkExpiredID'):
            del d['checkExpiredID']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self.touch()
        self.checkExpired()

INIT_SESSION = 'session-init'

def _setSession(wrap, req, cook):
    req.session = wrap.sessions[cook]
    req.getSession = req.session._getSelf

class SessionWrapper(Resource):

    def __init__(self, rsrc, cookieKey=None):
        Resource.__init__(self)
        self.resource = rsrc
        if cookieKey is None:
            cookieKey = "woven_session_" + _sessionCookie()
        self.cookieKey = cookieKey
        self.sessions = {}

    def render(self, request):
        return redirectTo(addSlash(request), request)

    def getChild(self, path, request):
        # XXX refactor with PerspectiveWrapper
        if not request.prepath:
            return None
        pp = request.prepath.pop()
        _urlToMe = request.prePathURL()
        request.prepath.append(pp)
        def urlToChild(*ar):
            c = '/'.join(ar)
            if _urlToMe[-1] == '/':
                # this SHOULD only happen in the case where the URL is just the hostname
                return _urlToMe + c
            else:
                return _urlToMe + '/' + c
        # XXX
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
                rd = Redirect(urlToChild(*request.postpath) +
                              # this next bit prevents 'redirect cycles' in
                              # wget (and possibly other browsers)
                              "?__session_just_started__=1")
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
            sz = self.sessions[newCookie] = GuardSession(self, newCookie)
            sz.checkExpired()
            return rd
        else:
            # /sessionized-url/foo
            #                 ^ we are this getChild
            # without a session
            request.getSession = lambda interface=None: None
            return self.resource.getChildWithDefault(path, request)

INIT_PERSPECTIVE = 'perspective-init'
DESTROY_PERSPECTIVE = 'perspective-destroy'

from twisted.python import formmethod as fm
from twisted.web.woven import form

loginSignature = fm.MethodSignature(
    fm.String("identity", "",
              "Identity", "The unique name of your account."),
    fm.Password("password", "",
                "Password", "The creative name of your password."),
    fm.String("perspective", None, "Perspective",
              "(Optional) The name of the role within your account "
              "you wish to perform."))

class PerspectiveWrapper(Resource):
    """I am a wrapper that will restrict access to Resources based on a
    C{twisted.cred.service.Service}'s 'authorizer' and perspective list.

    Please note that I must be in turn wrapped by a SessionWrapper, since my
    login functionality requires a session to be established.
    """
    
    def __init__(self, service, noAuthResource, authResourceFactory, callback=None):
        """Create a PerspectiveWrapper.
        
        @type service: C{twisted.cred.service.Service}

        @type noAuthResource: C{Resource}

        @type authResourceFactory: a callable object

        @param authResourceFactory: This should be a function which takes as an
        argument perspective from 'service' and returns a
        C{Resource} instance.

        @param noAuthResource: This parameter is the C{Resource} that is used
        when the user is browsing this site anonymously.  Somewhere accessible
        from this should be a link to 'perspective-init', which will display a
        C{form.FormProcessor} that allows the user to log in.
        """
        Resource.__init__(self)
        self.service = service
        self.noAuthResource = noAuthResource
        self.authResourceFactory = authResourceFactory
        self.callback = callback

    def getChild(self, path, request):
        s = request.getSession()
        if s is None:
            return request.setupSession()

        if path == INIT_PERSPECTIVE:
            def loginMethod(identity, password, perspective=None):
                idfr = self.service.authorizer.getIdentityRequest(identity)
                idfr.addCallback(
                    lambda ident:
                    ident.verifyPlainPassword(password).
                    addCallback(lambda ign:
                                ident.requestPerspectiveForService(self.service.serviceName))
                    .addCallback(lambda psp:
                                 s.setClientForService(ident, psp,
                                                       self.authResourceFactory(psp),
                                                       self.service)))
                def loginFailure(f):
                    if f.trap(Unauthorized):
                        raise fm.FormException(str(f.value))
                    raise f
                idfr.addErrback(loginFailure)
                return idfr
                
            return form.FormProcessor(
                loginSignature.method(loginMethod), 
                callback=self.callback)
        elif path == DESTROY_PERSPECTIVE:
            s.setClientForService(None, None, None, self.service)
            return Redirect(".")
        else:
            sc = s.clientForService(self.service)
            if sc:
                return sc.getChildWithDefault(path, request)
            return self.noAuthResource.getChildWithDefault(path, request)

newLoginSignature = fm.MethodSignature(
    fm.String("username", "",
              "Username", "Your user name."),
    fm.Password("password", "",
                "Password", "Your password.")
    )

from twisted.cred.credentials import UsernamePassword, Anonymous
import tapestry

class UsernamePasswordWrapper(Resource):
    def __init__(self, portal):
        Resource.__init__(self)
        self.portal = portal

    def startLoggingIn(self, username, password, session):
        return self.portal.login(UsernamePassword(username, password),
                                 None, IResource).addCallback(
            lambda (interface, avatarAspect, logout):
            session.setResourceForPortal(avatarAspect, self.portal, logout))

    def _ebFilter(self, f):
        f.trap(LoginFailed, UnauthorizedLogin)
        raise fm.FormException(str(f.value))

    def getChild(self, path, request):
        s = request.getSession()
        if s is None:
            return request.setupSession()
        if path == INIT_PERSPECTIVE:
            return form.FormProcessor(
                newLoginSignature.method(
                lambda username, password:
                self.startLoggingIn(username, password, s).addErrback(
                self._ebFilter
                )))
        elif path == DESTROY_PERSPECTIVE:
            s.portalLogout(self.portal)
            return Redirect(".")
        else:
            r = s.resourceForPortal(self.portal)
            if r:
                return r[0]
            else:
                return tapestry._ChildJuggler(
                    self.portal.login(Anonymous(), None, IResource
                                      ).addCallback(
                    lambda (interface, avatarAspect, logout):
                    s.setResourceForPortal(avatarAspect,
                                           self.portal, logout)))


from twisted.web.woven import interfaces, utils
## Dumb hack until we have an ISession and use interface-to-interface adaption
components.registerAdapter(utils.WovenLivePage, GuardSession, interfaces.IWovenLivePage)

