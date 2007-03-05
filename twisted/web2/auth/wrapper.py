# -*- test-case-name: twisted.web2.test.test_httpauth -*-

"""
Wrapper Resources for rfc2617 HTTP Auth.
"""
from zope.interface import implements, directlyProvides
from twisted.cred import error, credentials
from twisted.python import failure
from twisted.web2 import responsecode
from twisted.web2 import http
from twisted.web2 import iweb
from twisted.web2.auth.interfaces import IAuthenticatedRequest

class UnauthorizedResponse(http.StatusResponse):
    """A specialized response class for generating www-authenticate headers
    from the given L{CredentialFactory} instances
    """

    def __init__(self, factories, remoteAddr=None):
        """
        @param factories: A L{dict} of {'scheme': ICredentialFactory}

        @param remoteAddr: An L{IAddress} for the connecting client.
        """

        super(UnauthorizedResponse, self).__init__(
            responsecode.UNAUTHORIZED,
            "You are not authorized to access this resource.")

        authHeaders = []
        for factory in factories.itervalues():
            authHeaders.append((factory.scheme,
                                factory.getChallenge(remoteAddr)))

        self.headers.setHeader('www-authenticate', authHeaders)


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

    def _loginSucceeded(self, avatar, request):
        """
        Callback for successful login.

        @param avatar: A tuple of the form (interface, avatar) as
            returned by your realm.

        @param request: L{IRequest} that encapsulates this auth
            attempt.

        @return: the IResource in C{self.wrappedResource}
        """
        request.avatarInterface, request.avatar = avatar

        directlyProvides(request, IAuthenticatedRequest)

        def _addAuthenticateHeaders(request, response):
            """
            A response filter that adds www-authenticate headers
            to an outgoing response if it's code is UNAUTHORIZED (401)
            and it does not already have them.
            """
            if response.code == responsecode.UNAUTHORIZED:
                if not response.headers.hasHeader('www-authenticate'):
                    newResp = UnauthorizedResponse(self.credentialFactories,
                                                   request.remoteAddr)

                    response.headers.setHeader(
                        'www-authenticate',
                        newResp.headers.getHeader('www-authenticate'))

            return response

        _addAuthenticateHeaders.handleErrors = True

        request.addResponseFilter(_addAuthenticateHeaders)

        return self.wrappedResource

    def _loginFailed(self, result, request):
        """
        Errback for failed login.

        @param result: L{Failure} returned by portal.login

        @param request: L{IRequest} that encapsulates this auth
            attempt.

        @return: A L{Failure} containing an L{HTTPError} containing the
            L{UnauthorizedResponse} if C{result} is an L{UnauthorizedLogin}
            or L{UnhandledCredentials} error
        """
        result.trap(error.UnauthorizedLogin, error.UnhandledCredentials)

        return failure.Failure(
            http.HTTPError(
                UnauthorizedResponse(
                self.credentialFactories,
                request.remoteAddr)))

    def login(self, factory, response, request):
        """
        @param factory: An L{ICredentialFactory} that understands the given
            response.

        @param response: The client's authentication response as a string.

        @param request: The request that prompted this authentication attempt.

        @return: A L{Deferred} that fires with the wrappedResource on success
            or a failure containing an L{UnauthorizedResponse}
        """
        try:
            creds = factory.decode(response, request)
        except error.LoginFailed:
            raise http.HTTPError(UnauthorizedResponse(
                                    self.credentialFactories,
                                    request.remoteAddr))


        return self.portal.login(creds, None, *self.interfaces
                                ).addCallbacks(self._loginSucceeded,
                                               self._loginFailed,
                                               (request,), None,
                                               (request,), None)

    def authenticate(self, request):
        """
        Attempt to authenticate the givin request

        @param request: An L{IRequest} to be authenticated.
        """
        authHeader = request.headers.getHeader('authorization')

        if authHeader is None:
            return self.portal.login(credentials.Anonymous(),
                                     None,
                                     *self.interfaces
                                     ).addCallbacks(self._loginSucceeded,
                                                    self._loginFailed,
                                                    (request,), None,
                                                    (request,), None)

        elif authHeader[0] not in self.credentialFactories:
            raise http.HTTPError(UnauthorizedResponse(
                                    self.credentialFactories,
                                    request.remoteAddr))
        else:
            return self.login(self.credentialFactories[authHeader[0]],
                              authHeader[1], request)

    def locateChild(self, request, seg):
        """
        Authenticate the request then return the C{self.wrappedResource}
        and the unmodified segments.
        """
        return self.authenticate(request), seg

    def renderHTTP(self, request):
        """
        Authenticate the request then return the result of calling renderHTTP
        on C{self.wrappedResource}
        """
        def _renderResource(resource):
            return resource.renderHTTP(request)

        d = self.authenticate(request)
        d.addCallback(_renderResource)

        return d
