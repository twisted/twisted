# -*- test-case-name: twisted.test.test_woven -*-
"""Resource protection for Woven. If you wish to use twisted.cred to protect
your Woven application, you are probably most interested in
L{UsernamePasswordWrapper}.
"""

from __future__ import nested_scopes

__version__ = "$Revision: 1.24 $"[11:-2]

import random
import time
import md5

# Twisted Imports

from twisted.python import log, components
from twisted.web.resource import Resource, IResource
from twisted.web.util import redirectTo, Redirect, DeferredResource
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

class UsernamePasswordWrapper(Resource):
    """I bring a C{twisted.cred} Portal to the web. Use me to provide different Resources
    (usually entire pages) based on a user's authentication details.

    A C{UsernamePasswordWrapper} is a
    L{Resource<twisted.web.resource.Resource>}, and is usually wrapped in a
    L{SessionWrapper} before being inserted into the site tree.

    The L{Realm<twisted.cred.portal.IRealm>} associated with your
    L{Portal<twisted.cred.portal.Portal>} should be prepared to accept a
    request for an avatar that implements the L{twisted.web.resource.IResource}
    interface. This avatar should probably be something like a Woven
    L{Page<twisted.web.woven.page.Page>}. That is, it should represent a whole
    web page. Once you return this avatar, requests for it's children do not go
    through guard.

    If you want to determine what unauthenticated users see, make sure your
    L{Portal<twisted.cred.portal.Portal>} has a checker associated that allows
    anonymous access. (See L{twisted.cred.checkers.AllowAnonymousAccess})
    
    """
    
    def __init__(self, portal, callback=None, errback=None):
        """Constructs a UsernamePasswordWrapper around the given portal.

        @param portal: A cred portal for your web application. The checkers
            associated with this portal must be able to accept username/password
            credentials.
        @type portal: L{twisted.cred.portal.Portal}
        
        @param callback: I don't know what this callback does
        @type callback: A callable (WHAT ARE IT'S ARGS)

        @param errback: I don't know what this errback does
        @type errback: A callable (WHAT ARE IT'S ARGS)
        """
        Resource.__init__(self)
        self.portal = portal
        self.callback = callback
        self.errback = errback

    def _ebFilter(self, f):
        f.trap(LoginFailed, UnauthorizedLogin)
        raise fm.FormException(str(f.value))

    def getChild(self, path, request):
        s = request.getSession()
        if s is None:
            return request.setupSession()
        if path == INIT_PERSPECTIVE:
            def loginSuccess(result):
                interface, avatarAspect, logout = result
                s.setResourceForPortal(avatarAspect, self.portal, logout)

            def triggerLogin(username, password):
                return self.portal.login(
                    UsernamePassword(username, password),
                    None, 
                    IResource
                ).addCallback(
                    loginSuccess
                ).addErrback(
                    self._ebFilter
                )

            return form.FormProcessor(
                newLoginSignature.method(
                    triggerLogin
                ),
                callback=self.callback,
                errback=self.errback
            )
        elif path == DESTROY_PERSPECTIVE:
            s.portalLogout(self.portal)
            return Redirect(".")
        else:
            r = s.resourceForPortal(self.portal)
            if r:
                ## Delegate our getChild to the resource our portal says is the right one.
                return r[0].getChildWithDefault(path, request)
            else:
                return DeferredResource(
                    self.portal.login(Anonymous(), None, IResource
                                      ).addCallback(
                    lambda (interface, avatarAspect, logout):
                    s.setResourceForPortal(avatarAspect,
                                           self.portal, logout))).getChildWithDefault(path, request)


from twisted.web.woven import interfaces, utils
## Dumb hack until we have an ISession and use interface-to-interface adaption
components.registerAdapter(utils.WovenLivePage, GuardSession, interfaces.IWovenLivePage)

