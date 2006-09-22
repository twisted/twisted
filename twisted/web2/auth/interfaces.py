from zope.interface import Interface, Attribute

class ICredentialFactory(Interface):
    scheme = Attribute("string indicated the authentication scheme this factory is associated with.")

    def getChallenge(peer):
        """Generate a challenge the client may respond to.

        @type peer: L{twisted.internet.interfaces.IAddress}
        @param peer: The client's address

        @rtype: C{dict}
        @return: dictionary of challenge arguments
        """

    def decode(response, request):
        """Create a credentials object from the given response.
        May raise twisted.cred.error.LoginFailed if the response is invalid.
    
        @type response: C{str}
        @param response: scheme specific response string

        @type request: L{twisted.web2.server.Request}
        @param request: the request being processed

        @return: ICredentials
        """
