
from twisted.spread import pb
from twisted.python import log
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.cred import credentials
from twisted.application import service
from twisted.application import internet

import unix
import pbold
import jelliers

class FileDescriptorReceiver(protocol.Protocol):
    def __init__(self):
        self.fds = []

    def fileDescriptorsReceived(self, fds):
        self.fds.extend(fds)

    def __str__(self):
        return '<FileDescriptorReceiver (received %r)>' % (self.fds,)

class ClientFactory(protocol.ClientFactory):
    protocol = FileDescriptorReceiver

    def __init__(self, d):
        self.onConnect = d

    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        self.onConnect.callback(p)
        return p

def cbOwnedServer(result):
    print 'Owned server'

def cbGetServer(port, avatar, sname):
    return avatar.callRemote('gotServer', sname
        ).addCallback(cbOwnedServer
        ).addErrback(log.err
        )

def cbServerList(lst, avatar):
    sname = lst.pop()
    return avatar.callRemote('getServer', sname,
        ).addCallback(cbGetServer, avatar, sname
        ).addErrback(log.err
        )

def ebServerList(failure):
    log.err(failure)

def cbMigrate(avatar):
    # avatar.broker.transport.
    return avatar.callRemote('allocateDescriptorChannel'
        ).addCallback(cbDescriptorChannel, avatar
        ).addErrback(log.err
        )

def cbDescriptorChannel(channel, avatar):
    d = defer.Deferred()
    client = unix.UNIXClient(channel, ClientFactory(d), 10)
    client.startService()
    d.addCallback(cbChannelConnected, avatar)
    d.addErrback(log.err)
    return d

def cbChannelConnected(proto, avatar):
    # Hack!  But a much smaller one than what it replaced.
    avatar.broker.fdproto = proto
    return avatar.callRemote('getServerList'
        ).addCallback(cbServerList, avatar
        ).addErrback(ebServerList
        )

def makeService():
    cfac = pb.PBClientFactory()
    client = internet.UNIXClient('migrate', cfac, 10)
    cfac.login(credentials.UsernamePassword('user', 'pass')
        ).addCallback(cbMigrate
        ).addErrback(log.err
        #).addBoth(lambda _: reactor.stop()
        )
    return client

def main():
    a = service.Application("Service Migration Client")
    makeService().setServiceParent(a)
    return a

application = main()
