from socket import AF_INET, SOCK_STREAM # temporary, hopefully
from socket import socket

from twisted.internet import defer

# async op does:
# issue with user defined parameters
# TODO: how is this handled on the ITransport level?
# write callbacks with bytes written
# read callbacks with (bytes_read, dict_of_optional_data), for example recvfrom address or ancillary crud
# accept callbacks with newsock (not supporting insane AcceptEx initial read behavior... yet)

class AsyncOp(defer.Deferred):
    def initiateOp(self):
        raise NotImplementedError

class OverlappedOp(AsyncOp):
    def __init__(self):
        AsyncOp.__init__(self)
        from twisted.internet import reactor
        self.reactor = reactor

    def ovDone(self, ret, bytes):
        del self.handle
        del self.buffer
        # TODO: errback if ret is not good, for example cancelled
        self.callback(bytes)

class ReadFileOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        (ret, bytes) = self.reactor.issueReadFile(handle, buffer, self.ovDone)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class WriteFileOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        (ret, bytes) = self.reactor.issueWriteFile(handle, buffer, self.ovDone)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class WSARecvOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        (ret, bytes) = self.reactor.issueWSARecv(handle, buffer, self.ovDone)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class WSASendOp(OverlappedOp):
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        (ret, bytes) = self.reactor.WSASend(handle, buffer, self.ovDone)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)


class AcceptExOp(OverlappedOp):
    list = None
    def ovDone(self, ret, bytes):
        self.callback(self.list)

    def initiateOp(self, handle):
        # TODO: how do I determine these? from handle somehow?
        # create this socket in C code and return it from issueAcceptEx
        # also, determine size and create buffer there. No reason to propagate that idiocy into Python
        self.list = socket(AF_INET, SOCK_STREAM)
        self.buffer = self.reactor.AllocateReadBuffer(64) # save a reference so that things don't blow up
        self.handle = handle
        (ret, bytes) = self.reactor.issueAcceptEx(handle, self.list.fileno(), self.buffer, self.ovDone)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

