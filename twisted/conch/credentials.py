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

IUsernamePassword = credentials.IUsernamePassword
UsernamePassword = credentials.UsernamePassword
