from twisted.cred import credentials

class ISSHPrivateKey(credentials.ICredentials):
    """I encapsulate an SSH public key to be checked against a users private
    key.

    @ivar username: Duh?

    @ivar blob: The public key blob as sent by the client.

    @ivar sigData: The data the signature was made from.

    @ivar signature: The signed data.  This is checked to verify that the user
                     owns the private key.
    
    """

class SSHPrivateKey:
    __implements__ = ISSHPrivateKey
    def __init__(self, username, blob, sigData, signature):
        self.username = username
        self.blob = blob
        self.sigData = sigData
        self.signature = signature

class IPluggableAuthenticationModules(credentials.ICredentials):
    """I encapsulate the authentication of a user via PAM (Pluggable
    Authentication Modules.  I use PyPAM (available from
    http://www.tummy.com/Software/PyPam/index.html).

    @ivar username: The username for the user being logged in.

    @ivar pamConversion: A function that is called with a list of tuples 
                         (message, messageType).  See the PAM documentation
                         for the meaning of messageType.  The function
                         returns a Deferred which will fire with a list
                         of (response, 0), one for each message.  The 0 is
                         currently unused, but is required by the PAM library.
    """

class PluggableAuthenticationModules:
    __implements__ = IPluggableAuthenticationModules

    def __init__(self, username, pamConversion):
        self.username = username
        self.pamConversion = pamConversion

IUsernamePassword = credentials.IUsernamePassword
UsernamePassword = credentials.UsernamePassword
