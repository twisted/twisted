
from twisted.spread import pb
from twisted.internet import main, app

class PBBenchPerspective(pb.Perspective):
    def perspective_simple(self):
        return None

    def perspective_complexTypes(self):
        return ['a', 1, 1l, 1.0, [], ()]

class PBBenchService(pb.Service):
    perspectiveClass = PBBenchPerspective

a = app.Application("pbbench")
a.listenTCP(8787, pb.BrokerFactory(pb.AuthRoot(a)))
b = PBBenchService("benchmark", a)
b.createPerspective("benchmark").makeIdentity("benchmark")
a.run()
