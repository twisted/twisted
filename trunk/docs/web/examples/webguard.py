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

from zope.interface import implements

from twisted.python import log
from twisted.internet import reactor
from twisted.web import server, resource, guard
from twisted.cred.portal import IRealm, Portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse


class GuardedResource(resource.Resource):
    """
    A resource which is protected by guard and requires authentication in order
    to access.
    """
    def getChild(self, path, request):
        return self


    def render(self, request):
        return "Authorized!"



class SimpleRealm(object):
    """
    A realm which gives out L{GuardedResource} instances for authenticated
    users.
    """
    implements(IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            return resource.IResource, GuardedResource(), lambda: None
        raise NotImplementedError()



def main():
    log.startLogging(sys.stdout)
    checkers = [InMemoryUsernamePasswordDatabaseDontUse(joe='blow')]
    wrapper = guard.HTTPAuthSessionWrapper(
        Portal(SimpleRealm(), checkers),
        [guard.DigestCredentialFactory('md5', 'example.com')])
    reactor.listenTCP(8889, server.Site(
          resource = wrapper))
    reactor.run()

if __name__ == '__main__':
    main()
