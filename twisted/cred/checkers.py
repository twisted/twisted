# -*- test-case-name: twisted.test.test_newcred -*-

# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitza
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from twisted.internet import defer
from twisted.python import components, failure, log
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
        Alternatively, return the result itself.
        """

# A note on anonymity - We do not want None as the value for anonymous
# because it is too easy to accidentally return it.  We do not want the
# empty string, because it is too easy to mistype a password file.  For
# example, an .htpasswd file may contain the lines: ['hello:asdf',
# 'world:asdf', 'goodbye', ':world'].  This misconfiguration will have an
# ill effect in any case, but accidentally granting anonymous access is a
# worse failure mode than simply granting access to an untypeable
# username.  We do not want an instance of 'object', because that would
# create potential problems with persistence.

ANONYMOUS = ()


class AllowAnonymousAccess:
    __implements__ = ICredentialsChecker
    credentialInterfaces = credentials.IAnonymous,

    def requestAvatarId(self, credentials):
        return defer.succeed(ANONYMOUS)


class InMemoryUsernamePasswordDatabaseDontUse:
    __implements__ = ICredentialsChecker

    credentialInterfaces = (credentials.IUsernamePassword,
        credentials.IUsernameHashedPassword)

    def __init__(self, **users):
        self.users = users

    def addUser(self, username, password):
        self.users[username] = password

    def _cbPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())

    def requestAvatarId(self, credentials):
        if credentials.username in self.users:
            return defer.maybeDeferred(
                credentials.checkPassword,
                self.users[credentials.username]).addCallback(
                self._cbPasswordMatch, credentials.username)
        else:
            return failure.Failure(error.UnauthorizedLogin())


class FilePasswordDB:
    """A file-based, text-based username/password database.

    Records in the datafile for this class are delimited by a particular
    string.  The username appears in a fixed field of the columns delimited
    by this string, as does the password.  Both fields are specifiable.  If
    the passwords are not stored plaintext, a hash function must be supplied
    to convert plaintext passwords to the form stored on disk and this
    CredentialsChecker will only be able to check IUsernamePassword
    credentials.  If the passwords are stored plaintext,
    IUsernameHashedPassword credentials will be checkable as well.
    """

    __implements__ = (ICredentialsChecker,)

    def __init__(self, filename, delim=':', usernameField=0, passwordField=1,
                 caseSensitive=True, hash=None):
        """
        @type filename: C{str}
        @param filename: The name of the file from which to read username and
        password information.

        @type delim: C{str}
        @param delim: The field delimiter used in the file.

        @type usernameField: C{int}
        @param usernameField: The index of the username after splitting a
        line on the delimiter.

        @type caseSensitive: C{bool}
        @param caseSensitive: If true, consider the case of the username when
        performing a lookup.  Ignore it otherwise.

        @type passwordField: C{int}
        @param passwordField: The index of the password after splitting a
        line on the delimiter.

        @type hash: Three-argument callable.
        @param hash: A function used to transform the plaintext password
        received over the network to a format suitable for comparison against
        the version stored on disk.  The arguments to the callable are the
        username, the network-supplied password, and the in-file version of
        the password.
        """
        self.filename = filename
        self.delim = delim
        self.ufield = usernameField
        self.pfield = passwordField
        self.caseSensitive = caseSensitive
        self.hash = hash

        if self.hash is None:
            # The passwords are stored plaintext.  We can support both
            # plaintext and hashed passwords received over the network.
            self.credentialInterfaces = (
                credentials.IUsernamePassword,
                credentials.IUsernameHashedPassword
            )
        else:
            # The passwords are hashed on disk.  We can support only
            # plaintext passwords received over the network.
            self.credentialInterfaces = (
                credentials.IUsernamePassword,
            )


    def _cbPasswordMatch(self, matched, username):
        if matched:
            return username
        else:
            return failure.Failure(error.UnauthorizedLogin())

    def getUser(self, username):
        try:
            f = file(self.filename)
        except:
            log.err()
            raise error.UnauthorizedLogin()
        else:
            if not self.caseSensitive:
                username = username.lower()
            for line in f:
                line = line.rstrip()
                parts = line.split(self.delim)

                if self.ufield >= len(parts) or self.pfield >= len(parts):
                    continue
                if self.caseSensitive:
                    if parts[self.ufield] != username:
                        continue
                elif parts[self.ufield].lower() != username:
                    continue

                return parts[self.ufield], parts[self.pfield]
            raise KeyError(username)


    def requestAvatarId(self, c):
        try:
            u, p = self.getUser(c.username)
        except KeyError:
            return failure.Failure(error.UnauthorizedLogin())
        else:
            up = credentials.IUsernamePassword(c, default=None)
            if self.hash:
                if up is not None:
                    h = self.hash(up.username, up.password, p)
                    if h == p:
                        return u
                return failure.Failure(error.UnauthorizedLogin())
            else:
                return defer.maybeDeferred(c.checkPassword, p
                    ).addCallback(self._cbPasswordMatch, u)

# For backwards compatibility
# Allow access as the old name.
OnDiskUsernamePasswordDatabase = FilePasswordDB
