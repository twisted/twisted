from socket import AF_INET, SOCK_STREAM # temporary, hopefully
from socket import socket, SOL_SOCKET
import struct

from twisted.internet import defer

from getsockinfo import getsockinfo

SO_UPDATE_ACCEPT_CONTEXT = 0x700B
SO_UPDATE_CONNECT_CONTEXT = 0x7010

# async op does:
# issue with user defined parameters
# TODO: how is this handled on the ITransport level?
# write callbacks with bytes written
# read callbacks with (bytes_read, dict_of_optional_data), for example recvfrom address or ancillary crud
# accept callbacks with newsock (not supporting insane AcceptEx initial read behavior)

class AsyncOp(defer.Deferred):
    def initiateOp(self):
        raise NotImplementedError

class OverlappedOp(AsyncOp):
    def __init__(self):
        AsyncOp.__init__(self)
        from twisted.internet import reactor
        self.reactor = reactor

    def handleError(self, ret, bytes):
        """if error, errback and return True. Return False otherwise"""
        # TODO: implement me
        return False

    def ovDone(self, ret, bytes):
        raise NotImplementedError

class ReadFileOp(OverlappedOp):
    def ovDone(self, ret, bytes):
        print "ReadFileOp.ovDone(%(ret)s, %(bytes)s)" % locals()
        if not self.handleError(ret, bytes):
            self.callback((bytes, {}))
        del self.buffer
        del self.handle

    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        print "in ReadFileOp.initiateOp, calling issueReadFileOp with (%(handle)r)" % locals()
        (ret, bytes) = self.reactor.issueReadFile(handle, buffer, self.ovDone)
        print "in ReadFileOp.initiateOp, issueReadFileOp returned (%(ret)s, %(bytes)s), handle %(handle)s" % locals()
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class WriteFileOp(OverlappedOp):
    def ovDone(self, ret, bytes):
        print "WriteFileOp.ovDone(%(ret)s, %(bytes)s)" % locals()
        if not self.handleError(ret, bytes):
            self.callback(bytes)
        del self.buffer
        del self.handle

    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        print "in WriteFileOp.initiateOp, calling issueWriteFileOp with (%(handle)r)" % locals()
        (ret, bytes) = self.reactor.issueWriteFile(handle, buffer, self.ovDone)
        print "in WriteFileOp.initiateOp, issueWriteFileOp returned (%(ret)s, %(bytes)s), handle %(handle)s" % locals()
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

# BROKEN STUFF
"""
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
"""

class AcceptExOp(OverlappedOp):
    def ovDone(self, ret, bytes):
        print "AcceptExOp.ovDone(%(ret)s, %(bytes)s)" % locals()
        print "    self.acc_sock.fileno() %s self.handle %s" % (self.acc_sock.fileno(), self.handle)
        if not self.handleError(ret, bytes):
            self.acc_sock.setsockopt(SOL_SOCKET, SO_UPDATE_ACCEPT_CONTEXT, struct.pack("I", self.handle))
            self.callback((self.acc_socket, self.acc_sock.getpeername()))
        del self.buffer
        del self.handle
        del self.acc_sock

    def initiateOp(self, sock):
        max_addr, family, type, protocol = reactor.getsockinfo(sock)
        self.acc_sock = socket(family, type, protocol)
        self.buffer = self.reactor.AllocateReadBuffer(max_addr*2 + 32)
        self.handle = sock.fileno()
        (ret, bytes) = self.reactor.issueAcceptEx(self.handle, self.acc_sock.fileno(), self.ovDone, self.buffer)
        print "in AcceptExOp.initiateOp, issueAcceptEx returned (%(ret)s, %(bytes)s)" % locals()
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile
        # also, errback if this ReadFile call throws up (perhaps call ovDone ourselves to automate cleanup?)

class ConnectExOp(OverlappedOp):
    def ovDone(self, ret, bytes):
        print "ConnectExOp.ovDone(%(ret)s, %(bytes)s)" % locals()
        print "    self.list.fileno() %s self.handle %s" % (self.list.fileno(), self.handle)
        if not self.handleError(ret, bytes):
            self.sock.setsockopt(SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, "")
            self.callback(None)
        del self.handle

    def initiateOp(self, sock, addr):
        max_addr, family, type, protocol = reactor.getsockinfo(sock)
        self.handle = sock.fileno()
        (ret, bytes) = self.reactor.issueConnectEx(self.handle, family, addr, self.ovDone)

