import sys
###################
###################
###################
sys.path.append("/home/exarkun/projects/python/Twisted/sandbox/exarkun/papers/2004/pycon/migration/pb")
import pb
import schema

from twisted.spread.pb import Avatar, PBServerFactory, PBClientFactory, IPerspective, IPBRoot
pb.Avatar = Avatar
pb.IPerspective = IPerspective
pb.PBServerFactory = PBServerFactory
pb.PBClientFactory = PBClientFactory
###################
###################
###################

from twisted.python import components

class ISliceable(components.Interface):
    def start(self):
        pass
    def slice(self):
        pass
    def finish(self):
        pass

class InterfacefulRootSlicer(pb.PBRootSlicer):
    def slicerFactoryForObject(self, obj):
        print 'slicerFactoryFor', obj
        slicerClass = pb.PBRootSlicer.slicerFactoryForObject(self, obj)
        if slicerClass is None:
            slicerClass = ISliceable(obj, default=None)
        return slicerClass

class InterfacefulBroker(pb.Broker):
    slicerClass = InterfacefulRootSlicer

    def __init__(self, isClient=1):
        pb.Broker.__init__(self)
        self.isClient = isClient
        self.names = {}

    def setNameForLocal(self, name, obj):
        self.names[name] = self.putObj(obj)

    def remoteForName(self, name):
        return pb.RemoteReference(self, 1)

    def connectionMade(self):
        print 'Conn', self.factory
        self.factory.clientConnectionMade(self)

class PBServerFactory(pb.PBServerFactory):
    protocol = InterfacefulBroker

class PBClientFactory(pb.PBClientFactory):
    protocol = InterfacefulBroker

    def _cbSendUsername(self, root, username, password, client):
        return root.callRemote("login", username=username
                               ).addCallback(self._cbResponse, password, client
                                             )

    def _cbResponse(self, (challenge, challenger), password, client):
        resp = respond(challenge, password)
        return challenger.callRemote("respond", response=resp, mind=client)

class Root:
    __implements__ = IPBRoot
    def rootObject(self, broker):
        return self

    def remote_ready(self, receiver):
        print 'Woo woo', receiver

    def getMethodSchema(self, methodname):
        return None
