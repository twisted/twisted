# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == "__main__":
    # Avoid using any names defined in the "__main__" module.
    from pbecho import main

    raise SystemExit(main())

from zope.interface import implementer

from twisted.cred.portal import IRealm
from twisted.spread import pb


class DefinedError(pb.Error):
    pass


class SimplePerspective(pb.Avatar):
    def perspective_echo(self, text):
        print("echoing", text)
        return text

    def perspective_error(self):
        raise DefinedError("exception!")

    def logout(self):
        print(self, "logged out")


@implementer(IRealm)
class SimpleRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective in interfaces:
            avatar = SimplePerspective()
            return pb.IPerspective, avatar, avatar.logout
        else:
            raise NotImplementedError("no interface")


def main():
    from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
    from twisted.cred.portal import Portal
    from twisted.internet import reactor

    portal = Portal(SimpleRealm())
    checker = InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser("guest", "guest")
    portal.registerChecker(checker)
    reactor.listenTCP(pb.portno, pb.PBServerFactory(portal))
    reactor.run()
