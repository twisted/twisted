from twisted.application import service, compat, internet
from twisted.internet import protocol
from twisted.python import util

from twisted.cred import error
from twisted.cred import portal
from twisted.cred import checkers
from twisted.cred import credentials

from twisted.conch.checkers import UNIXPasswordDatabase
from twisted import conch

import cred_example

application = service.Application('credit_check')

s = service.IServiceCollection(application)

r = cred_example.Realm()
p = portal.Portal(r)
c = UNIXPasswordDatabase()
p.registerChecker(c, credentials.IUsernamePassword)
#p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
f = cred_example.ServerFactory(p)

myServer = internet.TCPServer(4738, f)
myServer.setServiceParent(s)

# vim:ft=python
