
import socket

from twisted.python import reflect
from twisted.python import components
from twisted.spread import interfaces as ispread
from twisted.spread import jelly
from twisted.internet import interfaces as iinternet
from twisted.internet import defer

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

class FileDescriptorJellier(components.Adapter):
    __implements__ = (ispread.IJellyable,)

    def getStateFor(self, jellier):
        state = self.original.__dict__.copy()
        del state['socket']
        state['fileno'] = self.original.fileno()
        return state

    def jellyFor(self, jellier):
        self.original.stopReading()
        self.original.stopWriting()
        sxp = jellier.prepare(self.original)
        sxp.extend([
            reflect.qual(self.original.__class__),
            jellier.jelly(self.getStateFor(jellier))])
        return jellier.preserve(self.original, sxp)

components.registerAdapter(FileDescriptorJellier, iinternet.IFileDescriptor, ispread.IJellyable)

def socketInMyPocket(instance, attribute, fileno, addressFamily, socketType):
    d = defer.Deferred()
    def magic():
        skt = socket.fromfd(fileno, addressFamily, socketType)
        setattr(instance, attribute, skt)
        instance.fileno = skt.fileno
        instance.startReading()
        instance.startWriting()
        d.callback(True)
    from twisted.internet import reactor
    reactor.callLater(0, magic)
    return d

class _DummyClass:
    pass

def FileDescriptorUnjellier(unjellier, jellyList):
    klass = reflect.namedAny(jellyList[0])
    inst = _DummyClass()
    inst.__class__ = klass
    state = unjellier.unjelly(jellyList[1])
    fileno = state.pop('fileno')
    inst.__dict__ = state
    socketInMyPocket(inst, 'socket', fileno, klass.addressFamily, klass.socketType)
    return inst

portBase = 'twisted.internet.%s.Port'
for mod in ('tcp',):
    jelly.setUnjellyableForClass(portBase % mod, FileDescriptorUnjellier)
del portBase, mod
