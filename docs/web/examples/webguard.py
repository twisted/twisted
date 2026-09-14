# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example shows how to make simple web authentication.

To run the example:
    $ python webguard.py

When you visit http://127.0.0.1:8889/, the page will ask for an username &
password. See the code in main() to get the correct username & password!
"""

import sys

from zope.interface import implementer

from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor
from twisted.python import log
from twisted.web import guard, resource, server


class GuardedResource(resource.Resource):
    """
    A resource which is protected by guard and requires authentication in order
    to access.
    """

    def getChild(self, path, request):
        return self

    def render(self, request):
        return b"Authorized!"


@implementer(IRealm)
class SimpleRealm:
    """
    A realm which gives out L{GuardedResource} instances for authenticated
    users.
    """

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            return resource.IResource, GuardedResource(), lambda: None
        raise NotImplementedError()


def main():
    log.startLogging(sys.stdout)
    checkers = [InMemoryUsernamePasswordDatabaseDontUse(joe=b"blow")]
    wrapper = guard.HTTPAuthSessionWrapper(
        Portal(SimpleRealm(), checkers),
        [guard.DigestCredentialFactory("md5", b"example.com")],
    )
    reactor.listenTCP(8889, server.Site(resource=wrapper))
    reactor.run()


if __name__ == "__main__":
    main()
