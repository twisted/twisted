
from twisted.spread import pb
from twisted.python import log
from twisted.internet import defer
from twisted.internet import reactor
from twisted.cred import credentials
from twisted.application import service
from twisted.application import internet

from client import ClientFactory
import unix

def handleFailedOwn(failure, avatar, name):
    log.err(failure)
    return avatar.callRemote('nevermind', name)

def cbOwnedServer(result, port):
    print 'Owned server', port

def cbGetServer(port, avatar, sname):
    return avatar.callRemote('gotServer', sname
        ).addCallback(cbOwnedServer, port
        )

def cbServerList(lst, avatar):
    sname = lst.pop()
    return avatar.callRemote('getServer', sname,
        ).addCallback(cbGetServer, avatar, sname
        ).addErrback(handleFailedOwn, avatar, sname
        )

def cbMigrate(avatar):
    # avatar.broker.transport.
    return avatar.callRemote('allocateDescriptorChannel'
        ).addCallback(cbDescriptorChannel, avatar
        )

def cbDescriptorChannel(channel, avatar):
    d = defer.Deferred()
    client = unix.UNIXClient(channel, ClientFactory(d), 10)
    client.startService()
    d.addCallback(cbChannelConnected, avatar)
    return d

def cbChannelConnected(proto, avatar):
    # Hack!  But a much smaller one than what it replaced.
    avatar.broker.fdproto = proto
    return avatar.callRemote('getServerList'
        ).addCallback(cbServerList, avatar
        )

def makeService():
    cfac = pb.PBClientFactory()
    client = internet.UNIXClient('migrate', cfac, 10)
    cfac.login(credentials.UsernamePassword('user', 'pass')
        ).addCallback(cbMigrate
        ).addErrback(log.err
        )
    return client

def main():
    a = service.Application("Service Migration Client")
    makeService().setServiceParent(a)
    return a

application = main()
