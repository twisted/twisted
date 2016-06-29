#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Implement the realm for and run on port 8800 a PB service which allows both
anonymous and username/password based access.

Successful username/password-based login requests given an instance of
MyPerspective with a name which matches the username with which they
authenticated.  Success anonymous login requests are given an instance of
MyPerspective with the name "Anonymous".
"""

from __future__ import print_function

from sys import stdout

from zope.interface import implementer

from twisted.python.log import startLogging
from twisted.cred.checkers import ANONYMOUS, AllowAnonymousAccess
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor
from twisted.spread.pb import Avatar, IPerspective, PBServerFactory


class MyPerspective(Avatar):
    """
    Trivial avatar exposing a single remote method for demonstrative
    purposes.  All successful login attempts in this example will result in
    an avatar which is an instance of this class.

    @type name: C{str}
    @ivar name: The username which was used during login or C{"Anonymous"}
    if the login was anonymous (a real service might want to avoid the
    collision this introduces between anonoymous users and authenticated
    users named "Anonymous").
    """
    def __init__(self, name):
        self.name = name


    def perspective_foo(self, arg):
        """
        Print a simple message which gives the argument this method was
        called with and this avatar's name.
        """
        print("I am %s.  perspective_foo(%s) called on %s." % (
            self.name, arg, self))



@implementer(IRealm)
class MyRealm(object):
    """
    Trivial realm which supports anonymous and named users by creating
    avatars which are instances of MyPerspective for either.
    """
    def requestAvatar(self, avatarId, mind, *interfaces):
        if IPerspective not in interfaces:
            raise NotImplementedError("MyRealm only handles IPerspective")
        if avatarId is ANONYMOUS:
            avatarId = "Anonymous"
        return IPerspective, MyPerspective(avatarId), lambda: None



def main():
    """
    Create a PB server using MyRealm and run it on port 8800.
    """
    startLogging(stdout)

    p = Portal(MyRealm())

    # Here the username/password checker is registered.
    c1 = InMemoryUsernamePasswordDatabaseDontUse(user1="pass1", user2="pass2")
    p.registerChecker(c1)

    # Here the anonymous checker is registered.
    c2 = AllowAnonymousAccess()
    p.registerChecker(c2)

    reactor.listenTCP(8800, PBServerFactory(p))
    reactor.run()


if __name__ == '__main__':
    main()
