raise ImportError("FIXME: this file probably doesn't work.")
# (Or maybe just delete this file)

# -*- test-case-name: twisted.web2.test -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""Utilities that help dealing with Request objects.
"""

# System Imports
import time
import urllib 

# Twisted Imports
from twisted.internet import reactor, defer
from twisted.python import log, components
from zope.interface import implements

from twisted.web2 import iweb

def sibLink(req, name):
    "Return the text that links to a sibling of the requested resource."
    if req.postpath:
        return (len(req.postpath)*"../") + name
    else:
        return name

def childLink(req, name):
    "Return the text that links to a child of the requested resource."
    lpp = len(req.postpath)
    if lpp > 1:
        return ((lpp-1)*"../") + name
    if lpp == 1:
        return name
    if len(req.prepath) and req.prepath[-1]:
        return req.prepath[-1] + '/' + name
    else:
        return name

class IAppRoot(components.Interface):
    """attribute: root"""

class AppRoot:
    implements(IAppRoot)
    def __init__(self, request):
        url = prePathURL(request)
        self.root = url[:url.rindex("/")]

components.backwardsCompatImplements(AppRoot)
components.registerAdapter(AppRoot, iweb.IRequest, IAppRoot)

class ISession(components.Interface):
    pass

def getSession(request):
    cookiename = "_".join(['TWISTED_SESSION'] + self.sitepath)
    sessionCookie = request.getCookie(cookiename)
    if sessionCookie:
        try:
            return request.site.getSession(sessionCookie)
        except KeyError:
            pass
    session = Session(request.site, request.site.mkuid())
    site.setSession(session)
    request.addCookie(cookiename, session.uid, path='/')
    request.setComponent(ISession, session) # is this needed?
    return session

components.registerAdapter(getSession, iweb.IRequest, ISession)

def prePathURL(request):
    port = request.getHost().port
    if request.isSecure():
        default = 443
    else:
        default = 80
    if port == default:
        hostport = ''
    else:
        hostport = ':%d' % port
    return urllib.quote('http%s://%s%s/%s' % (
        request.isSecure() and 's' or '',
        request.getRequestHostname(),
        hostport,
        '/'.join(request.prepath)), "/:")

def URLPath(request):
    from twisted.python import urlpath
    return urlpath.URLPath.fromString(prePathURL(request))

class Session(components.Componentized):
    """A user's session with a system.

    This utility class contains only timeout functionality, but is used to
    represent a session.
    """
    timeout = 15*60

    def __init__(self, site, uid):
        """Initialize a session with a unique ID for that session.
        """
        components.Componentized.__init__(self)
        self.site = site
        self.uid = uid
        self.expireCallbacks = []
        self.touch()
        self.sessionNamespaces = {}
        reactor.callLater(self.timeout, self._checkExpired)

    def notifyOnExpire(self):
        """Call this callback when the session expires or logs out.
        """
        self.expireCallbacks.append(defer.Deferred())
        return self.expireCallbacks[-1]

    def expire(self):
        """Expire/logout of the session.
        """
        #log.msg("expired session %s" % self.uid)
        del self.site.sessions[self.uid]
        for c in self.expireCallbacks:
            c.callback(self)
        self.expireCallbacks = []

    def touch(self):
        self.lastModified = time.time()

    def _checkExpired(self):
        if time.time() - self.lastModified <= self.timeout:
            #log.msg("session given the will to live for 30 more minutes")
            reactor.callLater(self.timeout, self._checkExpired)
        if self.uid in self.site.sessions:
            self.expire()
