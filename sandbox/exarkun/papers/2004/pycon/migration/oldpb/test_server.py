
import tempfile

from twisted.spread import pb
from twisted.python import log
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.application import service
from twisted.cred import portal
from twisted.cred import checkers

import pbold
import jelliers
import unix

def makeAFactory():
    from twisted.web import server, static
    pb.globalSecurity.allowInstancesOf(server.Site)
    return server.Site(static.File('.'))

class ServerFactory(protocol.ServerFactory):
    protocol = protocol.Protocol

    def __init__(self, d):
        self.onConnect = d

    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)
        self.onConnect.callback(p)
        return p

class MigrationError(Exception):
    pass

class DescriptorChannelNotAllocated(MigrationError):
    pass

#
# Sequence of events:
#
# Server listens on 'migrate' unix socket
# Client connects to 'migrate' unix socket
# New Avatar allocated for this connection
# Client asks for a new descriptor channel via PB
# Server allocates a temporary file, listens on it as a unix socket,
#   and tells client name of file
# Client connects to temporary file
# Client requests list of services available for transfer
# Server responds with list
# Client selects services and requests it from server
# Server moves service into `in transit' holding pen
# Server returns service:
#   Objects reachable from service are jellied
#   FileDescriptors encountered are jellied using the adapters
#     in jelliers.py; their file descriptors are sent over the
#     descriptor channel with sendmsg()
# Client acknowledges receipt of service and associated file
#   descriptors
# Server dumps service from `in transit' holding pen
# If no services remain on server, server terminates

class MigrationServer(pb.Avatar):
    descriptorChannelAllocated = False

    def __init__(self, servers):
        self.servers = servers
        self.transition = {}

    def cbChannelAllocate(self, result):
        self.descriptorChannelAllocated = True
        self.dConnection = None
        self.dChannel = result

    def perspective_allocateDescriptorChannel(self):
        tmp = tempfile.mktemp()
        self.dConnection = defer.Deferred()
        self.dConnection.addCallback(self.cbChannelAllocate)
        self.dConnection.addErrback(log.err)
        self.dChannelServer = unix.UNIXServer(tmp, ServerFactory(self.dConnection))
        self.dChannelServer.startService()
        return tmp

    def perspective_getServerList(self):
        return self.servers.keys()

    def perspective_getServer(self, name):
        if not self.descriptorChannelAllocated:
            raise DescriptorChannelNotAllocated()
        self.transition[name] = self.servers.pop(name)
        return self.transition[name]

    def perspective_gotServer(self, name):
        server = self.transition.pop(name)
        server.socket.close()
        server.socket = None
        if not self.servers and not self.transition:
            from twisted.internet import reactor
            # reactor.stop()

class MigrationRealm:
    __implements__ = (portal.IRealm,)

    def __init__(self, servers):
        self.servers = servers

    def requestAvatar(self, avatarID, mind, *interfaces):
        assert pb.IPerspective in interfaces
        return pb.IPerspective, MigrationServer(self.servers), lambda: None

def makeService():
    port = reactor.listenTCP(0, makeAFactory())

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
