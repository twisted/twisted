
import socket

from twisted.python import log
from twisted.python import reflect
from twisted.python import components
from twisted.spread import interfaces as ispread
from twisted.spread import jelly
from twisted.internet import interfaces as iinternet
from twisted.internet import defer

# Support needed from TPTB
class IJanitor(components.Interface):
    def track(self, id, cleanup, revert):
        pass

    def cleanup(self, id):
        pass

    def revert(self, id):
        pass

#
# Blah MetaInterface is not type
#
class MetaInterfaceJellier(components.Adapter):
    __implements__ = (ispread.IJellyable,)

    def jellyFor(self, jellier):
        sxp = jellier.prepare(self.original)
        sxp.extend([
            'twisted.python.components.MetaInterface',
            reflect.qual(self.original.__class__)])
        return jellier.preserve(self.original, sxp)

components.registerAdapter(MetaInterfaceJellier, components.MetaInterface, ispread.IJellyable)

def MetaInterfaceUnjellier(unjellier, jellyList):
    return reflect.namedAny(jellyList[1])

jelly.setUnjellyableForClass('twisted.python.components.MetaInterface', MetaInterfaceUnjellier)

#
# Reactor jelly!
#
class ReactorJellier(components.Adapter):
    __implements__ = (ispread.IJellyable,)

    def jellyFor(self, jellier):
        sxp = jellier.prepare(self.original)
        sxp.append('twisted.internet.reactor')
        return jellier.preserve(self.original, sxp)

components.registerAdapter(ReactorJellier, iinternet.IReactorCore, ispread.IJellyable)

def ReactorUnjellier(unjellier, jellyList):
    from twisted.internet import reactor
    return reactor

jelly.setUnjellyableForClass('twisted.internet.reactor', ReactorUnjellier)

#
# Address jelly!
#
class AddressJellier(components.Adapter):
    __implements__ = (ispread.IJellyable,)
    
    def getStateFor(self, jellier):
        return vars(self.original)
    
    def jellyFor(self, jellier):
        sxp = jellier.prepare(self.original)
        sxp.extend([
            reflect.qual(self.original.__class__),
            jellier.jelly(self.getStateFor(jellier))])
        return jellier.preserve(self.original, sxp)

from twisted.internet import address
components.registerAdapter(AddressJellier, address.IPv4Address, ispread.IJellyable)
components.registerAdapter(AddressJellier, address.UNIXAddress, ispread.IJellyable)
components.registerAdapter(AddressJellier, address._ServerFactoryIPv4Address, ispread.IJellyable)

class _NewStyleDummy(object):
    pass

def AddressUnjellier(unjellier, jellyList):
    klass = reflect.namedAny(jellyList[0])
    inst = _NewStyleDummy()
    inst.__class__ = klass
    state = unjellier.unjelly(jellyList[1])
    inst.__dict__ = state

    return inst

jelly.setUnjellyableForClass('twisted.internet.address.IPv4Address', AddressUnjellier)
jelly.setUnjellyableForClass('twisted.internet.address.UNIXAddress', AddressUnjellier)
jelly.setUnjellyableForClass('twisted.internet.address._ServerFactoryIPv4Address', AddressUnjellier)

#
# File descriptor jelly!
#
class ISocketStorage(components.Interface):
    def put(self, socket):
        """Stash a socket for later retrieval.

        @rtype: C{int}
        @return: An opaque handle which can be used
        later to retrieve the given socket.
        """

    def get(self, uid):
        """Retrieve a previously stored socket.

        @rtype: C{socket}
        @return: The socket associated with the given
        uid.  Subsequent calls of this function with
        the same uid will fail.
        """

class SocketStorage(components.Adapter):
    __implements__ = (ISocketStorage,)

    def __init__(self, original):
        components.Adapter.__init__(self, original)
        self.skts = {}

    def put(self, socket):
        self.skts[socket.fileno()] = socket
        return socket.fileno()

    def get(self, uid):
        skt = self.skts[uid]
        del self.skts[uid]
        return skt

components.registerAdapter(SocketStorage, jelly._Jellier, ISocketStorage)

class FileDescriptorJellier(components.Adapter):
    __implements__ = (ispread.IJellyable,)

    def getStateFor(self, jellier):
        state = self.original.__dict__.copy()
        ISocketStorage(jellier).put(state['socket'])
        del state['socket']
        jellier.invoker.serializingPerspective.dChannel.transport.sendFileDescriptors([state['fileno']()])
        del state['fileno']
        return state

    def jellyFor(self, jellier):
        log.msg("Jellying %s" % (self.original,))
        self.original.stopReading()
        self.original.stopWriting()
        a = jellier.invoker.serializingPerspective
        j = IJanitor(a)
        j.track(a.sendingServerID,
                lambda: self.original.socket.close(),
                lambda: (self.original.startReading(), self.original.startWriting()))
        sxp = jellier.prepare(self.original)
        sxp.extend([
            reflect.qual(self.original.__class__),
            jellier.jelly(self.getStateFor(jellier))])
        return jellier.preserve(self.original, sxp)

components.registerAdapter(FileDescriptorJellier, iinternet.IFileDescriptor, ispread.IJellyable)

def handleToFileDescriptor(handle):
    return defer.succeed(handle)

def handleToSocket(handle, addressFamily, socketType):
    return handleToFileDescriptor(handle
        ).addCallback(socket.fromfd, addressFamily, socketType
        )

READ = 1
WRITE = 2
def socketInMyPocket(skt, instance, attribute, mode):
    setattr(instance, attribute, skt)
    instance.fileno = skt.fileno
    if mode & READ:
        instance.startReading()
    if mode & WRITE:
        instance.startWriting()

class _DummyClass:
    pass

class FileDescriptorUnjellier:
    def __init__(self, mode):
        self.mode = mode

    def __call__(self, unjellier, jellyList):
        log.msg("Unellying! %s" % (jellyList,))
        # Second half of the icky hack!
        fdproto = unjellier.invoker.fdproto
        klass = reflect.namedAny(jellyList[0])
        inst = _DummyClass()
        inst.__class__ = klass
        state = unjellier.unjelly(jellyList[1])
        inst.__dict__ = state

        # Groan.  All transports should provide this information.
        addressFamily = getattr(klass, 'addressFamily', socket.AF_INET)
        socketType = getattr(klass, 'socketType', socket.SOCK_STREAM)

        handleToSocket(fdproto.fds.pop(), addressFamily, socketType,
            ).addCallback(socketInMyPocket, inst, 'socket', self.mode
            ).addErrback(log.err
            )
        return inst

portBase = 'twisted.internet.%s.Port'
for mod in ('tcp',):
    jelly.setUnjellyableForClass(portBase % mod, FileDescriptorUnjellier(READ))
del portBase, mod

connBase = 'twisted.internet.%s.Server'
for mod in ('tcp',):
    jelly.setUnjellyableForClass(connBase % mod, FileDescriptorUnjellier(READ | WRITE))
