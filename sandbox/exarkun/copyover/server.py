import os
import sys
import struct
import socket
import tempfile
from os.path import join as opj

from types import FileType
from socket import SocketType

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import abstract
from twisted.internet import tcp
from twisted.internet import unix
from twisted.persisted import styles
from twisted.python import log
from twisted.spread import pb
from twisted.cred import portal
from twisted.cred import checkers
from twisted.protocols import basic
from twisted.internet import unix
from twisted.application import internet

sys.path.append("../../pahan/sendmsg")
from sendmsg import sendmsg
from sendmsg import SCM_RIGHTS

class Server(unix.Server):
    def sendFileDescriptors(self, fileno, data="Filler"):
        """
        @param fileno: An iterable of the file descriptors to pass.
        """
        payload = struct.pack("%di" % len(fileno), *fileno)
        r = sendmsg(self.fileno(), data, 0, (socket.SOL_SOCKET, SCM_RIGHTS, payload))
        return r

class Port(unix.Port):
    transport = Server

class UNIXServer(internet._AbstractServer):
    def getHost(self):
        return self._port.getHost()

    def _getPort(self):
        from twisted.internet import reactor
        return reactor.listenWith(Port, *self.args, **self.kwargs)

class _FileDescriptorPickler:

    def __init__(self, fdmap):
        self.fdmap = fdmap

    def __id(self, fileno):
        id = len(self.fdmap)
        self.fdmap[id] = fileno
        return id

    def persistent_id(self, obj):
        from twisted.internet import reactor
        if obj is reactor:
            return 'reactor'
        elif isinstance(obj, FileType):
            return '%d:file:%s' % (self.__id(obj.fileno()), obj.mode)
        elif isinstance(obj, SocketType):
            return '%d:socket' % (self.__id(obj.fileno()),)
        elif isinstance(obj, styles.Ephemeral):
            print 'Serializing ephemeral', obj
            return obj.__dict__.copy()
        else:
            return None

def FileDescriptorPickler(s, fdmap):
    ph = _FileDescriptorPickler(fdmap)
    p = pickle.Pickler(s)
    p.persistent_id = ph.persistent_id
    return p

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

class FileDescriptorSendingProtocol(basic.LineReceiver):
    """
    Must be used with L{Port} as the transport.
    """

    def __init__(self, idmap):
        self.idmap = idmap

    def lineReceived(self, line):
        try:
            files = self.idmap[int(line)]
        except ValueError:
            log.msg("Peer sent us a bogus ID")
        except KeyError:
            log.msg("Peer sent us an unassigned ID")
        except:
            log.err()
        else:
            files = files.items()
            files.sort()
            self.transport.sendFileDescriptors([f[1] for f in files])
            return
        
        self.transport.loseConnection()

class FileDescriptorSendingFactory(protocol.ServerFactory):
    protocol = FileDescriptorSendingProtocol

    def __init__(self, idmap):
        self.idmap = idmap

    def buildProtocol(self, addr):
        p = self.protocol(self.idmap)
        return p

class UserStateSender(pb.Avatar):
    id = 0
    
    def __init__(self, client):
        self.idmap = {}

        # PB Object for talking to our peer
        self.client = client
        
        self.dir = tempfile.mkdtemp()
        self.path = tempfile.mktemp(dir=self.dir)
        self.factory = FileDescriptorSendingFactory(self.idmap)
        self.server = UNIXServer(opj(self.dir, self.path), self.factory)
        self.server.startService()

        reactor.callLater(1, sendSomeState, self)

    def logout(self):
        self.server.stopService()
        # This is BUNK with a capital BUNK
        reactor.callLater(0, os.rmdir, self.dir)

    def sendUserState(self, state):
        """Transmit the given state to this service's peer.
        """
        d = {}
        s = StringIO.StringIO()
        p = FileDescriptorPickler(s, d)
        p.dump(state)
        state = s.getvalue()
        self.id += 1
        self.idmap[self.id] = d
        return self._sendUserStateWithID(self.id, state, opj(self.dir, self.path))
    
    def _sendUserStateWithID(self, id, state, path):
        return self.client.callRemote("takeResponsibility", id, state, path)

class Realm:
    __implements__ = (portal.IRealm,)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if pb.IPerspective not in interfaces:
            raise NotImplementedError
        a = UserStateSender(mind)
        return pb.IPerspective, a, a.logout

def sendSomeState(avatar):
    from twisted.web import server
    from twisted.web.woven import dirlist
    from twisted.internet import reactor
    port = reactor.listenTCP(19191, server.Site(dirlist.DirectoryLister(".")))
    avatar.sendUserState(port)

def main():
    log.startLogging(sys.stdout)
    r = Realm()
    p = portal.Portal(r)
    c = checkers.InMemoryUsernamePasswordDatabaseDontUse(username="password")
    p.registerChecker(c)
    f = pb.PBServerFactory(p)
    reactor.listenTCP(10301, f)
    reactor.run()

if __name__ == '__main__':
    main()
