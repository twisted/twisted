import sys

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from twisted.internet import reactor
from twisted.internet import defer
from twisted.spread import pb
from twisted.python import log
from twisted.cred import credentials
from twisted.internet import protocol
from twisted.internet import unix
from twisted.application import internet

sys.path.append("../../pahan/sendmsg")
from sendmsg import recvmsg

class Client(unix.Client):
    connected = True
    
    def connectionLost(self, reason):
        self.connected = False
        unix.Client.connectionLost(self, reason)

    def doRead(self):
        if not self.connected:
            return
        try:
            msg, flags, ancillary = recvmsg(self.fileno())
        except:
            log.msg('recvmsg():')
            log.err()
        else:
            buf = ancillary[0][2]
            fds = []
            while buf:
                fd, buf = buf[:4], buf[4:]
                fds.append(struct.unpack("i", fd)[0])
            try:
                self.protocol.fileDescriptorsReceived(fds)
            except:
                log.msg('protocol.fileDescriptorsReceived')
                log.err()
        return unix.Client.doRead(self)

class Connector(unix.Connector):
    def _makeTransport(self):
        return Client(self.address, self, self.reactor)

class UNIXClient(internet._AbstractClient):
    def _getConnection(self):
        print 'get connection'
        from twisted.internet import reactor
        return reactor.connectWith(Connector, *self.args, **self.kwargs)

class _FileDescriptorUnpickler:
    def __init__(self, fdmap):
        self.fdmap = fdmap
        self.fdmemo = {}

    def persistent_load(self, id):
        r = None
        id = int(id)
        kname, mode, id = id.split(":")
        if id in self.fdmemo:
            return self.fdmemo[id]
        if kname == "file":
            r = self.fdmemo[id] = os.fdopen(self.fdmap[id], mode)
        elif kname == "socket":
            r = self.fdmemo[id] = socket.fromfd(self.fdmap[id])
        return r

def FileDescriptorUnpickler(s, fdmap):
    ph = _FileDescriptorUnpickler(fdmap)
    p = pickle.Unpickler(s)
    p.persistent_load = ph.persistent_load
    return p

class FileDescriptorReceivingProtocol(protocol.Protocol):
    """
    Must be used with L{Port} as the transport.
    """
    
    def __init__(self, id, d):
        print 'hi'
        self.id = id
        self.d = d

    def connectionMade(self):
        print 'fie'
        self.transport.write("%s\r\n" % (self.id,))

    def dataReceived(self, data):
        print 'Got some random data', repr(data)

    def fileDescriptorsReceived(self, fds):
        print 'guy'
        self.d.callback(fds)
        self.transport.loseConnection()

class FileDescriptorRequestFactory(protocol.ClientFactory):
    protocol = FileDescriptorReceivingProtocol

    def __init__(self, id, d):
        print 'request factory'
        self.id = id
        self.gotFDs = d

    def buildProtocol(self, addr):
        print 'buildProtocol'
        p = self.protocol(self.id, self.gotFDs)
        return p

class UserStateReceiver(pb.Referenceable):
    def unproxyFileDescriptors(self, fds, state):
        print 'unproxying'
        s = StringIO.StringIO(state)
        p = FileDescriptorUnpickler(s, fds)
        return p.load()

    def remote_takeUser(self, id, state, path):
        print 'takeUser', id, state, path
        d = defer.Deferred()
        f = FileDescriptorRequestFactory(id, d)
        client = UNIXClient(path, f, 60).startService()
        d.addCallback(self.unproxyFileDescriptors, state)
        return d

def main():
    log.startLogging(sys.stdout)
    f = pb.PBClientFactory()
    reactor.connectTCP("localhost", 10301, f)
    f.login(credentials.UsernamePassword("username", "password"), UserStateReceiver())
    reactor.run()

if __name__ == '__main__':
    main()
