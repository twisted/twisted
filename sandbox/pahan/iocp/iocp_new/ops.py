from pywintypes import OVERLAPPED
from win32file import AllocateReadBuffer, AcceptEx, ReadFile, WriteFile, WSARecv, WSASend

from socket import AF_INET, SOCK_STREAM # temporary, hopefully
from socket import socket

from twisted.internet import defer

# async op does:
# issue with user defined parameters
# TODO: how is this handled on the ITransport level?
# ugh extra object creation overhead omfg (these are deferreds, not reusable, but perhaps make them so)
# write callbacks with bytes written
# read callbacks with (bytes_read, dict_of_optional_data), for example recvfrom address or ancillary crud

class AsyncOp(defer.Deferred):
    def initiateOp(self):
        raise NotImplementedError

class OverlappedOp(AsyncOp):
    def __init__(self):
        AsyncOp.__init__(self)
        self.ov = OVERLAPPED()
        self.ov.object = "ovDone"

    def ovDone(self, ret, bytes):
        from twisted.internet import reactor
        reactor.unregisterHandler(self.handle)
        del self.handle
        del self.buffer
        # TODO: errback if ret is not good, for example cancelled
        self.callback(bytes)

class ReadFileOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        # XXX: is this expensive to do? is this circular importing dangerous?
        from twisted.internet import reactor
        reactor.registerHandler(handle, self)
        (ret, bytes) = ReadFile(handle, buffer, self.ov)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class WriteFileOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        # XXX: is this expensive to do? is this circular importing dangerous?
        from twisted.internet import reactor
        reactor.registerHandler(handle, self)
        (ret, bytes) = WriteFile(handle, buffer, self.ov)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class WSARecvOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        # XXX: is this expensive to do? is this circular importing dangerous?
        from twisted.internet import reactor
        reactor.registerHandler(handle, self)
        (ret, bytes) = WSARecv(handle, buffer, self.ov, 0)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class WSASendOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        # XXX: is this expensive to do? is this circular importing dangerous?
        from twisted.internet import reactor
        reactor.registerHandler(handle, self)
        (ret, bytes) = WSASend(handle, buffer, self.ov, 0)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)


class AcceptExOp(OverlappedOp):
    list = None
    def ovDone(self, ret, bytes):
        OverlappedOp.ovDone(ret, bytes)

    def initiateOp(self, handle):
        self.list = socket(AF_INET, SOCK_STREAM) # TODO: how do I determine these? from handle somehow?
        self.buffer = AllocateReadBuffer(64) # save a reference so that things don't blow up
        self.handle = handle
        # XXX: is this expensive to do? is this circular importing dangerous?
        from twisted.internet import reactor
        reactor.registerHandler(handle, self)
        AcceptEx(handle, self.list, self.buffer, self.ov)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)
