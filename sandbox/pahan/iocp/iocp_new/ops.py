import struct, socket

from twisted.internet import defer
from twisted.python import log

from twisted import internet
import twisted.internet.error # this enables access to name "internet.error"

from getsockinfo import getsockinfo
import error

SO_UPDATE_ACCEPT_CONTEXT = 0x700B
SO_UPDATE_CONNECT_CONTEXT = 0x7010

# async op does:
# issue with user defined parameters
# write callbacks with bytes written
# read callbacks with (bytes_read, dict_of_optional_data), for example recvfrom address or ancillary crud
# accept callbacks with newsock (not supporting insane AcceptEx initial read behavior)

class OverlappedOp(defer.Deferred):
    handle = None
    buffer = None
    def __init__(self):
        defer.Deferred.__init__(self)
        from twisted.internet import reactor
        self.reactor = reactor

    def cleanUp(self):
        # TODO: remove from pending op list
        del self.handle
        del self.buffer

    def handleError(self, ret, bytes, fIo = True):
        """if error, errback and return True. Return False otherwise"""
#        if ret == 0:
#            if bytes == 0:
#                self.errback(error.HandleClosedException())
#                return True
#            else:
#                return False
#        else:
        if ret:
            if ret in (error.ERROR_INVALID_USER_BUFFER, error.ERROR_NOT_ENOUGH_MEMORY):
#                print "%s errbacks NonFatalException" % (self,)
                self.errback(error.NonFatalException())
            elif ret in (error.ERROR_OPERATION_ABORTED, error.ERROR_CONNECTION_ABORTED):
#                print "%s errbacks OperationCancelledException" % (self,)
                self.errback(error.OperationCancelledException())
            elif ret == error.ERROR_CONNECTION_REFUSED:
                self.errback(internet.error.ConnectionRefusedError())
            elif ret == error.ERROR_NETNAME_DELETED:
#                print "%s errbacks HandleClosedException" % (self,)
                self.errback(error.HandleClosedException())
            else:
#                print "%s errbacks UnknownException" % (self,)
                self.errback(error.UnknownException())
            return True
        elif fIo and bytes == 0:
#                print "%s errbacks HandleClosedException" % (self,)
                self.errback(internet.error.ConnectionDone())
                return True
        else:
            return False

    def ovDone(self, ret, bytes):
        raise NotImplementedError

    def initiateOp(self):
        # TODO: add to pending op list. But probably not here, need to do it after op is scheduled without error
        raise NotImplementedError

class ReadFileOp(OverlappedOp):
    def ovDone(self, ret, bytes):
        if __debug__:
            print "ReadFileOp.ovDone(%(ret)s, %(bytes)s)" % locals()
        if not self.handleError(ret, bytes):
            self.callback((bytes, {}))
        self.cleanUp()

    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        try:
#            print "in ReadFileOp.initiateOp, calling issueReadFileOp with (%(handle)r)" % locals()
            (ret, bytes) = self.reactor.issueReadFile(handle, buffer, self.ovDone)
#            print "in ReadFileOp.initiateOp, issueReadFileOp returned (%(ret)s, %(bytes)s), handle %(handle)s" % locals()
        except Exception:
            self.cleanUp()
            raise

class WriteFileOp(OverlappedOp):
    def ovDone(self, ret, bytes):
        if __debug__:
            print "WriteFileOp.ovDone(%(ret)s, %(bytes)s)" % locals()
        if not self.handleError(ret, bytes):
            self.callback(bytes)
        self.cleanUp()

    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        try:
#            print "in WriteFileOp.initiateOp, calling issueWriteFileOp with (%(handle)r)" % locals()
            (ret, bytes) = self.reactor.issueWriteFile(handle, buffer, self.ovDone)
#            print "in WriteFileOp.initiateOp, issueWriteFileOp returned (%(ret)s, %(bytes)s), handle %(handle)s" % locals()
        except Exception:
            self.cleanUp()
            raise

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
    acc_sock = None

    def ovDone(self, ret, bytes):
        if __debug__:
            print "AcceptExOp.ovDone(%(ret)s, %(bytes)s)" % locals()
#        print "    self.acc_sock.fileno() %s self.handle %s" % (self.acc_sock.fileno(), self.handle)
        if not self.handleError(ret, bytes, False):
            try:
                self.acc_sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_ACCEPT_CONTEXT, struct.pack("I", self.handle))
            # stab me in the eye with a fork (workaround similar to the one in ConnectExOp.ovDone)
            except socket.error, se:
                self.errback(internet.error.UserError())
                self.cleanUp
                return
#            print "AcceptExOp.ovDone callbacking with self.acc_sock %s, peername %s" % \
#                    (self.acc_sock._sock, self.acc_sock.getpeername())
            self.callback((self.acc_sock, self.acc_sock.getpeername()))
        self.cleanUp()

    def cleanUp(self):
        OverlappedOp.cleanUp(self)
        del self.acc_sock

    def initiateOp(self, sock):
        self.handle = sock.fileno()
        try:
            max_addr, family, type, protocol = self.reactor.getsockinfo(self.handle)
            self.acc_sock = socket.socket(family, type, protocol)
            self.buffer = self.reactor.AllocateReadBuffer(max_addr*2 + 32)
            (ret, bytes) = self.reactor.issueAcceptEx(self.handle, self.acc_sock.fileno(), self.ovDone, self.buffer)
#            print "in AcceptExOp.initiateOp, issueAcceptEx returned (%(ret)s, %(bytes)s)" % locals()
        except Exception:
            self.cleanUp()
            raise

class ConnectExOp(OverlappedOp):
    def ovDone(self, ret, bytes):
        if __debug__:
            print "ConnectExOp.ovDone(%(ret)s, %(bytes)s)" % locals()
        if not self.handleError(ret, bytes, False):
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, "")
            # Windows succeeds with ConnectEx even if the socket was closed before gqcs
            # this is a EBADF
            except socket.error, se:
                # irrelevant, because Connector is already cancelled, hopefully
                self.errback(internet.error.UserError())
                self.cleanUp()
                return
            self.callback(None)
        self.cleanUp()

    def cleanUp(self):
        del self.sock
        del self.handle

    def initiateOp(self, sock, addr):
        try:
            self.handle = sock.fileno()
            max_addr, family, type, protocol = self.reactor.getsockinfo(self.handle)
            self.sock = sock
            (ret, bytes) = self.reactor.issueConnectEx(self.handle, family, addr, self.ovDone)
        except Exception:
            self.cleanUp()
            raise

