# -*- test-case-name: twisted.web.test.test_woven -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""Resource protection for Woven. If you wish to use twisted.cred to protect
your Woven application, you are probably most interested in
L{UsernamePasswordWrapper}.
"""

from __future__ import nested_scopes

__version__ = "$Revision: 1.34 $"[11:-2]

import random
import time
import md5
import urllib

# Twisted Imports

from twisted.python import log, components
from twisted.web.resource import Resource, IResource
from twisted.web.util import redirectTo, Redirect, DeferredResource
from twisted.web.static import addSlash
from twisted.internet import reactor
from twisted.cred.error import LoginFailed, UnauthorizedLogin

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

def urlToChild(request, *ar, **kw):
    pp = request.prepath.pop()
    orig = request.prePathURL()
    request.prepath.append(pp)
    c = '/'.join(ar)
    if orig[-1] == '/':
        # this SHOULD only happen in the case where the URL is just the hostname
        ret = orig + c
    else:
        ret = orig + '/' + c
    args = request.args.copy()
    args.update(kw)
    if args:
        ret += '?'+urllib.urlencode(args)
    return ret

def redirectToSession(request, garbage):
    rd = Redirect(urlToChild(request, *request.postpath, **{garbage:1}))
    rd.isLeaf = 1
    return rd

SESSION_KEY='__session_key__'

class SessionWrapper(Resource):

    sessionLifetime = 1800
    
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
        if not request.prepath:
            return None
        cookie = request.getCookie(self.cookieKey)
        setupURL = urlToChild(request, INIT_SESSION, *([path]+request.postpath))
        request.setupSessionURL = setupURL
        request.setupSession = lambda: Redirect(setupURL)
        if path.startswith(SESSION_KEY):
            key = path[len(SESSION_KEY):]
            if key not in self.sessions:
                return redirectToSession(request, '__start_session__')
            self.sessions[key].setLifetime(self.sessionLifetime)
            if cookie == key:
                # /sessionized-url/${SESSION_KEY}aef9c34aecc3d9148/foo
                #                  ^
                #                  we are this getChild
                # with a matching cookie
                return redirectToSession(request, '__session_just_started__')
            else:
                # We attempted to negotiate the session but failed (the user
                # probably has cookies disabled): now we're going to return the
                # resource we contain.  In general the getChild shouldn't stop
                # there.
                # /sessionized-url/${SESSION_KEY}aef9c34aecc3d9148/foo
                #                  ^ we are this getChild
                # without a cookie (or with a mismatched cookie)
                _setSession(self, request, key)
                return self.resource
        elif cookie in self.sessions:
            # /sessionized-url/foo
            #                 ^ we are this getChild
            # with a session
            _setSession(self, request, cookie)
            return getResource(self.resource, path, request)
        elif path == INIT_SESSION:
            # initialize the session
            # /sessionized-url/session-init
            #                  ^ this getChild
            # without a session
            newCookie = _sessionCookie()
            request.addCookie(self.cookieKey, newCookie, path="/")
            sz = self.sessions[newCookie] = GuardSession(self, newCookie)
            sz.checkExpired()
            rd = Redirect(urlToChild(request, SESSION_KEY+newCookie,
                                              *request.postpath))
            rd.isLeaf = 1
            return rd
        else:
            # /sessionized-url/foo
            #                 ^ we are this getChild
            # without a session
            request.getSession = lambda interface=None: None
            return getResource(self.resource, path, request)

def getResource(resource, path, request):
    if resource.isLeaf:
        request.postpath.insert(0, request.prepath.pop())
        return resource
    else:
        return resource.getChildWithDefault(path, request)

INIT_PERSPECTIVE = 'perspective-init'
DESTROY_PERSPECTIVE = 'perspective-destroy'

from twisted.python import formmethod as fm
from twisted.web.woven import form


newLoginSignature = fm.MethodSignature(
    fm.String("username", "",
              "Username", "Your user name."),
    fm.Password("password", "",
                "Password", "Your password."),
    fm.Submit("submit", choices=[("Login", "", "")], allowNone=1),
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
        
        @param callback: Gets called after a successful login attempt.
            A resource that redirects to "." will display the avatar resource.
            If this parameter isn't provided, defaults to a standard Woven
            "Thank You" page.
        @type callback: A callable that accepts a Woven
            L{model<twisted.web.woven.interfaces.IModel>} and returns a
            L{IResource<twisted.web.resource.Resource>}.

        @param errback: Gets called after a failed login attempt.
            If this parameter is not provided, defaults to a the standard Woven
            form error (i.e. The original form on a page of its own, with
            errors noted.)
        @type errback: A callable that accepts a Woven
            L{model<twisted.web.woven.interfaces.IModel>} and returns a
            L{IResource<twisted.web.resource.Resource>}.
        """
        Resource.__init__(self)
        self.portal = portal
        self.callback = callback
        self.errback = errback

    def _ebFilter(self, f):
        f.trap(LoginFailed, UnauthorizedLogin)
        raise fm.FormException(password="Login failed, please enter correct username and password.")

    def getChild(self, path, request):
        s = request.getSession()
        if s is None:
            return request.setupSession()
        if path == INIT_PERSPECTIVE:
            def loginSuccess(result):
                interface, avatarAspect, logout = result
                s.setResourceForPortal(avatarAspect, self.portal, logout)

            def triggerLogin(username, password, submit=None):
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
                return getResource(r[0], path, request)
            else:
                return DeferredResource(
                    self.portal.login(Anonymous(), None, IResource
                                      ).addCallback(
                    lambda (interface, avatarAspect, logout):
                    getResource(s.setResourceForPortal(avatarAspect,
                                           self.portal, logout),
                                path, request)))



from twisted.web.woven import interfaces, utils
## Dumb hack until we have an ISession and use interface-to-interface adaption
components.registerAdapter(utils.WovenLivePage, GuardSession, interfaces.IWovenLivePage)

