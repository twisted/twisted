
from twisted.python import log
from twisted.spread import pb
from twisted.application import service
from twisted.application import internet
from twisted.cred import checkers
from twisted.cred import portal

import unix
import pbold
import jelliers

from server import MigrationRealm

def makeAFactory():
    from twisted.web import server, static
    pb.globalSecurity.allowInstancesOf(server.Site)
    return server.Site(static.File('.'))

def makeService():
    from twisted.internet import reactor
    port = reactor.listenTCP(8000, makeAFactory())

    r = MigrationRealm({'blah': port})
    p = portal.Portal(r)
    p.registerChecker(checkers.FilePasswordDB('passwd'))

    svr = unix.UNIXServer('migrate', pb.PBServerFactory(p, True))
    return svr

def main():
    a = service.Application("Service Migration Server")
    makeService().setServiceParent(a)
    return a

application = main()
