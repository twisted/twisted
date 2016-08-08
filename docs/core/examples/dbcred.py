#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Simple example of a db checker: define a L{ICredentialsChecker} implementation
that deals with a database backend to authenticate a user.
"""

from twisted.cred import error
from twisted.cred.credentials import IUsernameHashedPassword, IUsernamePassword
from twisted.cred.checkers import ICredentialsChecker
from twisted.internet.defer import Deferred

from zope.interface import implementer


@implementer(ICredentialsChecker)
class DBCredentialsChecker(object):
    """
    This class checks the credentials of incoming connections
    against a user table in a database.
    """
    def __init__(self, runQuery,
        query="SELECT username, password FROM user WHERE username = %s",
        customCheckFunc=None, caseSensitivePasswords=True):
        """
        @param runQuery: This will be called to get the info from the db.
            Generally you'd want to create a
            L{twisted.enterprice.adbapi.ConnectionPool} and pass it's runQuery
            method here. Otherwise pass a function with the same prototype.
        @type runQuery: C{callable}

        @type query: query used to authenticate user.
        @param query: C{str}

        @param customCheckFunc: Use this if the passwords in the db are stored
            as hashes. We'll just call this, so you can do the checking
            yourself. It takes the following params:
            (username, suppliedPass, dbPass) and must return a boolean.
        @type customCheckFunc: C{callable}

        @param caseSensitivePasswords: If true requires that every letter in
            C{credentials.password} is exactly the same case as the it's
            counterpart letter in the database.
            This is only relevant if C{customCheckFunc} is not used.
        @type caseSensitivePasswords: C{bool}
        """
        self.runQuery = runQuery
        self.caseSensitivePasswords = caseSensitivePasswords
        self.customCheckFunc = customCheckFunc
        # We can't support hashed password credentials if we only have a hash
        # in the DB
        if customCheckFunc:
            self.credentialInterfaces = (IUsernamePassword,)
        else:
            self.credentialInterfaces = (
                IUsernamePassword, IUsernameHashedPassword,)

        self.sql = query

    def requestAvatarId(self, credentials):
        """
        Authenticates the kiosk against the database.
        """
        # Check that the credentials instance implements at least one of our
        # interfaces
        for interface in self.credentialInterfaces:
            if interface.providedBy(credentials):
                break
        else:
            raise error.UnhandledCredentials()
        # Ask the database for the username and password
        dbDeferred = self.runQuery(self.sql, (credentials.username,))
        # Setup our deferred result
        deferred = Deferred()
        dbDeferred.addCallbacks(self._cbAuthenticate, self._ebAuthenticate,
                callbackArgs=(credentials, deferred),
                errbackArgs=(credentials, deferred))
        return deferred

    def _cbAuthenticate(self, result, credentials, deferred):
        """
        Checks to see if authentication was good. Called once the info has
        been retrieved from the DB.
        """
        if len(result) == 0:
            # Username not found in db
            deferred.errback(error.UnauthorizedLogin('Username unknown'))
        else:
            username, password = result[0]
            if self.customCheckFunc:
                # Let the owner do the checking
                if self.customCheckFunc(
                        username, credentials.password, password):
                    deferred.callback(credentials.username)
                else:
                    deferred.errback(
                        error.UnauthorizedLogin('Password mismatch'))
            else:
                # It's up to us or the credentials object to do the checking
                # now
                if IUsernameHashedPassword.providedBy(credentials):
                    # Let the hashed password checker do the checking
                    if credentials.checkPassword(password):
                        deferred.callback(credentials.username)
                    else:
                        deferred.errback(
                            error.UnauthorizedLogin('Password mismatch'))
                elif IUsernamePassword.providedBy(credentials):
                    # Compare the passwords, deciging whether or not to use
                    # case sensitivity
                    if self.caseSensitivePasswords:
                        passOk = (
                            password.lower() == credentials.password.lower())
                    else:
                        passOk = password == credentials.password
                    # See if they match
                    if passOk:
                        deferred.callback(credentials.username)
                    else:
                        deferred.errback(
                            error.UnauthorizedLogin('Password mismatch'))
                else:
                    # OK, we don't know how to check this
                    deferred.errback(error.UnhandledCredentials())

    def _ebAuthenticate(self, message, credentials, deferred):
        """
        The database lookup failed for some reason.
        """
        deferred.errback(error.LoginFailed(message))


def main():
    """
    Run a simple echo pb server to test the checker. It defines a custom query
    for dealing with sqlite special quoting, but otherwise it's a
    straightforward use of the object.

    You can test it running C{pbechoclient.py}.
    """
    import sys
    from twisted.python import log
    log.startLogging(sys.stdout)
    import os
    if os.path.isfile('testcred'):
        os.remove('testcred')
    from twisted.enterprise import adbapi
    pool = adbapi.ConnectionPool('pysqlite2.dbapi2', 'testcred')
    # Create the table that will be used
    query1 = """CREATE TABLE user (
            username string,
            password string
        )"""
    # Insert a test user
    query2 = """INSERT INTO user VALUES ('guest', 'guest')"""
    def cb(res):
        pool.runQuery(query2)
    pool.runQuery(query1).addCallback(cb)

    checker = DBCredentialsChecker(pool.runQuery,
        query="SELECT username, password FROM user WHERE username = ?")
    from twisted.cred.portal import Portal

    import pbecho
    from twisted.spread import pb
    portal = Portal(pbecho.SimpleRealm())
    portal.registerChecker(checker)
    reactor.listenTCP(pb.portno, pb.PBServerFactory(portal))


if __name__ == "__main__":
    from twisted.internet import reactor
    reactor.callWhenRunning(main)
    reactor.run()

