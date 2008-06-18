# -*- test-case-name: twisted.web.test.test_httpauth -*-
# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A guard implementation which supports HTTP header-based authentication
schemes.

If either no www-authenticate header is present in the request or the
supplied response is invalid a status code of 401 will be sent in the
response along with all accepted authentication schemes.
"""

from zope.interface import implements

from twisted.python import log
from twisted.python.components import proxyForInterface
from twisted.web.resource import IResource
from twisted.web import util
from twisted.web.error import ErrorPage
from twisted.cred import error as credError


class UnauthorizedResource(object):
    """
    Simple IResource to escape Resource dispatch
    """
    implements(IResource)
    isLeaf = True


    def __init__(self, factories):
        self._credentialFactories = factories


    def render(self, request):
        """
        Send www-authenticate headers to the client
        """
        def generateWWWAuthenticate(scheme, challenge):
            l = []
            for k,v in challenge.iteritems():
                l.append("%s=%s" % (k, quoteString(v)))
            return "%s %s" % (scheme, ", ".join(l))

        def quoteString(s):
            return '"%s"' % (s.replace('\\', '\\\\').replace('"', '\\"'),)

        request.setResponseCode(401)
        for fact in self._credentialFactories:
            challenge = fact.getChallenge(request)
            request.responseHeaders.addRawHeader(
                'www-authenticate',
                generateWWWAuthenticate(fact.scheme, challenge))
        return 'Unauthorized'


    def getChildWithDefault(self, path, request):
        """
        Disable resource dispatch
        """
        return self



class HTTPAuthSessionWrapper(object):
    """
    Wrap a portal, enforcing supported header-based authentication schemes.

    @ivar _portal: The L{Portal} which will be used to retrieve L{IResource}
        avatars.

    @ivar _credentialFactories: A list of L{ICredentialFactory} providers which
        will be used to decode I{Authorization} headers into L{ICredentials}
        providers.
    """
    implements(IResource)
    isLeaf = False

    def __init__(self, portal, credentialFactories):
        """
        Initialize a session wrapper

        @type portal: C{Portal}
        @param portal: The portal that will authenticate the remote client

        @type credentialFactories: C{Iterable}
        @param credentialFactories: The portal that will authenticate the
            remote client based on one submitted C{ICredentialFactory}
        """
        self._portal = portal
        self._credentialFactories = credentialFactories


    def render(self, request):
        raise NotImplementedError


    def getChildWithDefault(self, path, request):
        """
        Inspect the Authorization HTTP header, and return a deferred which,
        when fired after successful authentication, will return an authorized
        C{Avatar}. On authentication failure, an C{UnauthorizedResource} will
        be returned, essentially halting further dispatch on the wrapped
        resource and all children
        """
        authheader = request.getHeader('authorization')
        if not authheader:
            return UnauthorizedResource(self._credentialFactories)

        factory, respString = self._selectParseHeader(authheader)
        if factory is None:
            return UnauthorizedResource(self._credentialFactories)
        try:
            credentials = factory.decode(respString, request)
        except credError.LoginFailed:
            return UnauthorizedResource(self._credentialFactories)
        except:
            log.err(None, "Unexpected failure from credentials factory")
            return ErrorPage(500, None, None)
        else:
            return util.DeferredResource(self._login(credentials))


    def _login(self, credentials):
        """
        Get the L{IResource} avatar for the given credentials.

        @return: A L{Deferred} which will be called back with an L{IResource}
            avatar or which will errback if authentication fails.
        """
        d = self._portal.login(credentials, None, IResource)
        d.addCallbacks(self._loginSucceeded, self._loginFailed)
        return d


    def _loginSucceeded(self, (interface, avatar, logout)):
        """
        Handle login success by wrapping the resulting L{IResource} avatar
        so that the C{logout} callback will be invoked when rendering is
        complete.
        """
        class ResourceWrapper(proxyForInterface(IResource, 'resource')):
            """
            Wrap an L{IResource} so that whenever it or a child of it
            completes rendering, the cred logout hook will be invoked.

            An assumption is made here that exactly one L{IResource} from
            among C{avatar} and all of its children will be rendered.  If
            more than one is rendered, C{logout} will be invoked multiple
            times and probably earlier than desired.
            """
            def getChildWithDefault(self, name, request):
                """
                Pass through the lookup to the wrapped resource, wrapping
                the result in L{ResourceWrapper} to ensure C{logout} is
                called when rendering of the child is complete.
                """
                return ResourceWrapper(self.resource.getChildWithDefault(name, request))

            def render(self, request):
                """
                Hook into response generation so that when rendering has
                finished completely, C{logout} is called.
                """
                request.notifyFinish().addCallback(lambda ign: logout())
                return super(ResourceWrapper, self).render(request)

        return ResourceWrapper(avatar)


    def _loginFailed(self, result):
        """
        Handle login failure by presenting either another challenge (for
        expected authentication/authorization-related failures) or a server
        error page (for anything else).
        """
        if result.check(credError.Unauthorized, credError.LoginFailed):
            return UnauthorizedResource(self._credentialFactories)
        else:
            log.err(
                result,
                "HTTPAuthSessionWrapper.getChildWithDefault encountered "
                "unexpected error")
            return ErrorPage(500, None, None)


    def _selectParseHeader(self, header):
        """
        Choose an C{ICredentialFactory} from C{_credentialFactories}
        suitable to use to decode the given I{Authenticate} header.

        @return: A two-tuple of a factory and the remaining portion of the
            header value to be decoded or a two-tuple of C{None} if no
            factory can decode the header value.
        """
        elements = header.split(' ')
        scheme = elements[0].lower()
        for fact in self._credentialFactories:
            if fact.scheme == scheme:
                return (fact, ' '.join(elements[1:]))
        return (None, None)
