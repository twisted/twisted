from zope.interface import Interface, Attribute

class ICredentialFactory(Interface):
    """
    A credential factory provides state between stages in HTTP
    authentication.  It is ultimately in charge of creating an
    ICredential for the specified scheme, that will be used by
    cred to complete authentication.
    """
    scheme = Attribute(("string indicating the authentication scheme "
                        "this factory is associated with."))

    def getChallenge(peer):
        """
        Generate a challenge the client may respond to.

        @type peer: L{twisted.internet.interfaces.IAddress}
        @param peer: The client's address

        @rtype: C{dict}
        @return: dictionary of challenge arguments
        """

    def decode(response, request):
        """
        Create a credentials object from the given response.
        May raise twisted.cred.error.LoginFailed if the response is invalid.

        @type response: C{str}
        @param response: scheme specific response string

        @type request: L{twisted.web2.server.Request}
        @param request: the request being processed

        @return: ICredentials
        """


class IAuthenticatedRequest(Interface):
    """
    A request that has been authenticated with the use of Cred,
    and holds a reference to the avatar returned by portal.login
    """

    avatarInterface = Attribute(("The credential interface implemented by "
                                 "the avatar"))

    avatar = Attribute("The application specific avatar returned by "
                       "the application's realm")


class IHTTPUser(Interface):
    """
    A generic interface that can implemented by an avatar to provide
    access to the username used when authenticating.
    """

    username = Attribute(("A string representing the username portion of "
                          "the credentials used for authentication"))