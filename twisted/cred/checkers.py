# -*- test-case-name: twisted.test.test_newcred -*-

from twisted.internet import defer
from twisted.python import components, failure
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
        avatar, an empty tuple to specify an authenticated anonymous user
        (provided as checkers.ANONYMOUS) or fire a Failure(UnauthorizedLogin).
        A note on anonymity - We do not want None as the value for anonymous
        because it is too easy to accidentally return it.  We do not want the
        empty string, because it is too easy to mistype a password file.  For
        example, an .htpasswd file may contain the lines: ['hello:asdf',
        'world:asdf', 'goodbye', ':world'].  This misconfiguration will have an
        ill effect in any case, but accidentally granting anonymous access is a
        worse failure mode than simply granting access to an untypeable
        username.  We do not want an instance of 'object', because that would
        create potential problems with persistence.
        """

ANONYMOUS = ()

class AllowAnonymousAccess:
    __implements__ = ICredentialsChecker
    credentialInterfaces = credentials.IAnonymous,

    def requestAvatarId(self, credentials):
        return defer.succeed(ANONYMOUS)

class InMemoryUsernamePasswordDatabaseDontUse:
    credentialInterfaces = credentials.IUsernamePassword,
    __implements__ = ICredentialsChecker
    def __init__(self):
        self.users = {}

    def addUser(self, username, password):
        self.users[username] = password

    def _cbPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())

    def requestAvatarId(self, credentials):
        if self.users.has_key(credentials.username):
            return defer.maybeDeferred(
                credentials.checkPassword,
                self.users[credentials.username]).addCallback(
                self._cbPasswordMatch, credentials.username)
        else:
            return defer.fail(error.UnauthorizedLogin())

        
