
from twisted.spread import pb
from twisted.python import log
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.cred import credentials
from twisted.application import service

import unix
import pbold
import jelliers

class FileDescriptorReceiver(protocol.Protocol):
    def __init__(self):
        self.fds = []

    def fileDescriptorReceived(self, fds):
        print 'Some fds', fds
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

def cbGetServer(port, avatar, proto, sname):
    print 'Server acheived!'
    print sname, port, avatar, proto
    return avatar.callRemote('gotServer', sname)

def cbServerList(lst, avatar, proto):
    sname = lst.pop()
    return avatar.callRemote('getServer', sname,
        ).addCallback(cbGetServer, avatar, proto, sname
        ).addErrback(log.err
        )

def ebServerList(failure):
    log.err(failure)

def cbMigrate(avatar):
    # avatar.broker.transport.
    print vars(avatar)
    return avatar.callRemote('allocateDescriptorChannel'
        ).addCallback(cbDescriptorChannel, avatar
        ).addErrback(log.err
        )

def cbDescriptorChannel(channel, avatar):
    print 'Here we are, yo'
    d = defer.Deferred()
    client = unix.UNIXClient(channel, ClientFactory(d), 10)
    client.startService()
    d.addCallback(cbChannelConnected, avatar)
    d.addErrback(log.err)
    return d

def cbChannelConnected(proto, avatar):
    return avatar.callRemote('getServerList'
        ).addCallback(cbServerList, avatar, proto
        ).addErrback(ebServerList
        )

def makeService():
    cfac = pb.PBClientFactory()
    client = unix.UNIXClient('migrate', cfac, 10)
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
