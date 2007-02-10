# -*- test-case-name: twisted.web2.test.test_httpauth -*-

"""
Wrapper Resources for rfc2617 HTTP Auth.
"""
from zope.interface import implements, directlyProvides
from twisted.cred import error
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

    def login(self, factory, response, req):
        """
        @param factory: An L{ICredentialFactory} that understands the given
            response.

        @param response: The client's authentication response as a string.

        @param request: The request that prompted this authentication attempt.

        @return: A L{Deferred} that fires with the wrappedResource on success
            or a failure containing an L{UnauthorizedResponse}
        """
        def _loginSucceeded(avatar):
            # Login succeeded so attach the avatar and interface to
            # the request.  Then note that the request now provides
            # IAuthenticatedRequest and return the wrappedResource

            req.avatarInterface, req.avatar = avatar

            directlyProvides(req, IAuthenticatedRequest)

            return self.wrappedResource

        def _loginFailed(res):
            # Return the unauthorized response with the appropriate
            # challenges for the credentialFactories
            res.trap(error.UnauthorizedLogin)

            return failure.Failure(
                http.HTTPError(
                    UnauthorizedResponse(
                    self.credentialFactories,
                    req.remoteAddr)))

        try:
            creds = factory.decode(response, req)
        except error.LoginFailed:
            raise http.HTTPError(UnauthorizedResponse(
                                    self.credentialFactories,
                                    req.remoteAddr))


        return self.portal.login(creds, None, *self.interfaces
                                ).addCallbacks(_loginSucceeded,
                                               _loginFailed)

    def authenticate(self, req):
        """
        Attempt to authenticate the givin request

        @param req: An L{IRequest} to be authenticated.
        """
        authHeader = req.headers.getHeader('authorization')

        if authHeader is None or authHeader[0] not in self.credentialFactories:
            raise http.HTTPError(UnauthorizedResponse(
                                    self.credentialFactories,
                                    req.remoteAddr))
        else:
            return self.login(self.credentialFactories[authHeader[0]],
                              authHeader[1], req)

    def locateChild(self, req, seg):
        # Authenticate the given request without modifying seg
        return self.authenticate(req), seg

    def renderHTTP(self, req):
        return self.authenticate(req)
