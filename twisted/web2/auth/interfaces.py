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

    def decode(response, method=None):
        """Create a credentials object from the given response.
        May raise twisted.cred.error.LoginFailed if the response is invalid.
    
        @type response: C{str}
        @param response: scheme specific response string

        @type method: C{str}
        @param method: the method by which this response was sent

        @return: ICredentials
        """
