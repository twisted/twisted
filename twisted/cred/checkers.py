
from twisted.internet import defer
from twisted.python import components
from twisted.cred import error, credentials

class ICredentialsChecker(components.Interface):
    """I check sub-interfaces of ICredentials.

    @cvar credentialInterfaces: A list of sub-interfaces of ICredentials which
    specifies which I may check.
    """

    def requestAvatarId(self, credentials):
        """
        @param credentials: something which implements one of the interfaces in
        self.credentialInterfaces.
        
        @return: a Deferred which will fire a string which identifies an
        avatar, or fire a Failure(UnauthorizedLogin).
        """

class InMemoryUsernamePasswordDatabaseDontUse:
    credentialInterfaces = credentials.IUsernamePassword,
    def __init__(self):
        self.users = {}

    def addUser(self, username, password):
        self.users[username] = password

    def requestAvatarId(self, credentials):
        if (self.users.has_key(credentials.username) and
            self.users[credentials.username] == credentials.password):
            return defer.succeed(credentials.username)
        else:
            return defer.fail(error.UnauthorizedLogin())
