import sys
###################
###################
###################
sys.path.append("../../warner")
import pb

from twisted.spread.pb import Avatar, PBServerFactory, PBClientFactory, IPerspective
pb.Avatar = Avatar
pb.IPerspective = IPerspective
pb.PBServerFactory = PBServerFactory
pb.PBClientFactory = PBClientFactory
###################
###################
###################

class ISliceable:
    def start(self):
        pass
    def slice(self):
        pass
    def finish(self):
        pass

class InterfacefulRootSlicer(pb.PBRootSlicer):
    def slicerFactoryForObject(self, obj):
        slicerClass = pb.PBRootSlicer.slicerFactoryForObject(self, obj)
        if slicerClass is None:
            slicerClass = ISliceable(obj, default=None)
        return slicerClass

class InterfacefulBroker(pb.Broker):
    slicerClass = InterfacefulRootSlicer

    def setNameForLocal(self, name, obj):
        pass

class PBServerFactory(pb.PBServerFactory):
    protocol = staticmethod(lambda ignore: InterfacefulBroker())

class PBClientFactory(pb.PBClientFactory):
    protocol = InterfacefulBroker
