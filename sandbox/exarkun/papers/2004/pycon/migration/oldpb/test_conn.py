
from twisted.python import log
from twisted.spread import pb
from twisted.application import service
from twisted.application import internet
from twisted.cred import checkers
from twisted.cred import portal

# from twisted.manhole import telnet
# pb.globalSecurity.allowInstancesOf(telnet.Shell)

import unix
import pbold
import jelliers

from server import MigrationRealm

def makeAFactory():
    from telnet import ShellFactory
    return ShellFactory()

def makeService():
    f = makeAFactory()
    from twisted.internet import reactor
    port = reactor.listenTCP(8000, f)

    r = MigrationRealm(f.protos)
    p = portal.Portal(r)
    p.registerChecker(checkers.FilePasswordDB('passwd'))

    svr = unix.UNIXServer('migrate', pb.PBServerFactory(p, True))
    return svr

def main():
    a = service.Application("Service Migration Server")
    makeService().setServiceParent(a)
    return a

application = main()
