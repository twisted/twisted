from twisted.application import service, internet
from twisted.spread import pb
from twisted.internet import defer
from twisted.cred.credentials import UsernamePassword
import time

class PBBenchClient:
    hostname = '192.168.203.128'
    portno = pb.portno
    calledThisSecond = 0

    def callLoop(self, ignored):
        d1 = self.persp.callRemote("simple")
        d2 = self.persp.callRemote("complexTypes")
        defer.DeferredList([d1, d2]).addCallback(self.callLoop)
        self.calledThisSecond += 1
        thisSecond = int(time.time())
        if thisSecond != self.lastSecond:
            if thisSecond - self.lastSecond > 1:
                print "WARNING it took more than one second"
            print 'cps:', self.calledThisSecond
            self.calledThisSecond = 0
            self.lastSecond = thisSecond

    def _cbPerspective(self, persp):
        self.persp = persp
        self.lastSecond = int(time.time())
        self.callLoop(None)

    def runTest(self):
        factory = pb.PBClientFactory()
        app = service.Application("pbc")
        c = internet.TCPClient(self.hostname, self.portno, factory)
        c.setServiceParent(service.IServiceCollection(app))
        factory.login(UsernamePassword("benchmark", "benchmark")).addCallback(self._cbPerspective)
        return app


def main():
    return PBBenchClient().runTest()

application = main()

