
from twisted.spread import pb
from twisted.internet import main, app

class PBBenchPerspective(pb.Perspective):
    callsPerSec = 0
    def perspective_simple(self):
        self.callsPerSec = self.callsPerSec + 1
        return None

    def printCallsPerSec(self):
        print '(s) cps:', self.callsPerSec
        self.callsPerSec = 0
        main.addTimeout(self.printCallsPerSec, 1)

    def perspective_complexTypes(self):
        return ['a', 1, 1l, 1.0, [], ()]

class PBBenchService(pb.Service):
    perspectiveClass = PBBenchPerspective

a = app.Application("pbbench")
a.listenTCP(8787, pb.BrokerFactory(pb.AuthRoot(a)))
b = PBBenchService("benchmark", a)
u = b.createPerspective("benchmark")
u.makeIdentity("benchmark")
u.printCallsPerSec()
a.run()
