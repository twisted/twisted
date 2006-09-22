# -*- test-case-name: twisted.web2.test.test_httpauth -*-

"""
Wrapper Resources for rfc2617 HTTP Auth.
"""
from zope.interface import implements
from twisted.cred import error

from twisted.web2 import resource
from twisted.web2 import responsecode
from twisted.web2 import http
from twisted.web2 import iweb

class UnauthorizedResponse(http.StatusResponse):
    """A specialized response class for generating www-authenticate headers
    from the given L{CredentialFactory} instances
    """

    def __init__(self, factories, remoteAddr=None):
        super(UnauthorizedResponse, self).__init__(
            responsecode.UNAUTHORIZED,
            "You are not authorized to access this resource.")
        
        authHeaders = []
        for factory in factories.itervalues():
            authHeaders.append((factory.scheme,
                                factory.getChallenge(remoteAddr)))

        self.headers.setHeader('www-authenticate', authHeaders)


class UnauthorizedResource(resource.LeafResource):
    """Returned by locateChild or render to generate an http Unauthorized
       response.
    """

    def __init__(self, factories):
        """
        @param factories: sequence of ICredentialFactory implementations 
                          for which to generate a WWW-Authenticate header.
        """
        self.factories = factories
        
    def render(self, req):
        return UnauthorizedResponse(self.factories, req.remoteAddr)


class HTTPAuthResource(object):
    """I wrap a resource to prevent it being accessed unless the authentication
       can be completed using the credential factory, portal, and interfaces
       specified.
    """

    implements(iweb.IResource)

    def __init__(self, wrappedResource, credentialFactories,
                 portal, interfaces):
        """
        @param wrappedResource: A L{twisted.web2.iweb.IResource} to be returned 
                                from locateChild and render upon successful
                                authentication.

        @param credentialFactories: A list of instances that implement 
                                    L{ICredentialFactory}.
        @type credentialFactories: L{list}

        @param portal: Portal to handle logins for this resource.
        @type portal: L{twisted.cred.portal.Portal}
        
        @param interfaces: the interfaces that are allowed to log in via the 
                           given portal
        @type interfaces: L{tuple}
        """

        self.wrappedResource = wrappedResource

        self.credentialFactories = dict([(factory.scheme, factory) 
                                         for factory in credentialFactories])
        self.portal = portal
        self.interfaces = interfaces

    def login(self, factory, response, req):
        def _loginSucceeded(res):
            return self.wrappedResource

        def _loginFailed(res):
            return UnauthorizedResource(self.credentialFactories)

        try:
            creds = factory.decode(response, req)
        except error.LoginFailed:
            return UnauthorizedResource(self.credentialFactories)

        return self.portal.login(creds, None, *self.interfaces
                                ).addCallbacks(_loginSucceeded,
                                               _loginFailed)

    def authenticate(self, req):
        authHeader = req.headers.getHeader('authorization')

        if authHeader is None or authHeader[0] not in self.credentialFactories:
            return UnauthorizedResource(self.credentialFactories)
        else:
            return self.login(self.credentialFactories[authHeader[0]],
                              authHeader[1], req)

    def locateChild(self, req, seg):
        return self.authenticate(req), seg[1:]

    def renderHTTP(self, req):
        return self.authenticate(req)
