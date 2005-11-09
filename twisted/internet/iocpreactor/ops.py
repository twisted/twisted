# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import struct, socket, os, errno
#import time

from twisted.internet import error
from twisted.python import failure, log

from _iocp import have_connectex

SO_UPDATE_ACCEPT_CONTEXT = 0x700B
SO_UPDATE_CONNECT_CONTEXT = 0x7010

ERROR_CONNECTION_REFUSED = 1225
ERROR_INVALID_HANDLE = 6
ERROR_PIPE_ENDED = 109
ERROR_SEM_TIMEOUT = 121
ERROR_NETNAME_DELETED = 64

winerrcodeMapping = {ERROR_CONNECTION_REFUSED: errno.WSAECONNREFUSED}

class OverlappedOp:
    def __init__(self, transport):
        from twisted.internet import reactor
        self.reactor = reactor
        self.transport = transport

    def ovDone(self, ret, bytes, arg):
        raise NotImplementedError

    def initiateOp(self):
        raise NotImplementedError

class ReadFileOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer)):
        if ret or not bytes:
            self.transport.readErr(ret, bytes)
        else:
            self.transport.readDone(bytes)

    def initiateOp(self, handle, buffer):
        self.reactor.issueReadFile(handle, buffer, self.ovDone, (handle, buffer))

class WriteFileOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer)):
#        log.msg("WriteFileOp.ovDone", time.time())
        if ret or not bytes:
            self.transport.writeErr(ret, bytes)
        else:
            self.transport.writeDone(bytes)

    def initiateOp(self, handle, buffer):
#        log.msg("WriteFileOp.initiateOp", time.time())
        self.reactor.issueWriteFile(handle, buffer, self.ovDone, (handle, buffer))

class WSASendToOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer)):
        if ret or not bytes:
            self.transport.writeErr(ret, bytes)
        else:
            self.transport.writeDone(bytes)

    def initiateOp(self, handle, buffer, addr):
        max_addr, family, type, protocol = self.reactor.getsockinfo(handle)
        self.reactor.issueWSASendTo(handle, buffer, family, addr, self.ovDone, (handle, buffer))

class WSARecvFromOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer, ab)):
        if ret or not bytes:
            self.transport.readErr(ret, bytes)
        else:
            self.transport.readDone(bytes, self.reactor.interpretAB(ab))

    def initiateOp(self, handle, buffer):
        ab = self.reactor.AllocateReadBuffer(1024)
        self.reactor.issueWSARecvFrom(handle, buffer, ab, self.ovDone, (handle, buffer, ab))

class AcceptExOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer, acc_sock)):
        if ret in (ERROR_NETNAME_DELETED, ERROR_SEM_TIMEOUT):
            # yay, recursion
            self.initiateOp(handle)
        elif ret:
            self.transport.acceptErr(ret, bytes)
        else:
            try:
                acc_sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_ACCEPT_CONTEXT, struct.pack("I", handle))
            except socket.error, se:
                self.transport.acceptErr(ret, bytes)
            else:
                self.transport.acceptDone(acc_sock, acc_sock.getpeername())

    def initiateOp(self, handle):
        max_addr, family, type, protocol = self.reactor.getsockinfo(handle)
        acc_sock = socket.socket(family, type, protocol)
        buffer = self.reactor.AllocateReadBuffer(max_addr*2 + 32)
        self.reactor.issueAcceptEx(handle, acc_sock.fileno(), self.ovDone, (handle, buffer, acc_sock), buffer)

class ConnectExOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, sock)):
        if ret:
#            print "ConnectExOp err", ret
            self.transport.connectErr(failure.Failure(error.errnoMapping.get(winerrcodeMapping.get(ret), error.ConnectError)())) # finish the mapping in error.py
        else:
            if have_connectex:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, "")
                except socket.error, se:
                    self.transport.connectErr(failure.Failure(error.ConnectError()))
            self.transport.connectDone()

    def threadedDone(self, _):
        self.transport.connectDone()

    def threadedErr(self, err):
        self.transport.connectErr(err)

    def initiateOp(self, sock, addr):
        handle = sock.fileno()
        if have_connectex:
            max_addr, family, type, protocol = self.reactor.getsockinfo(handle)
            self.reactor.issueConnectEx(handle, family, addr, self.ovDone, (handle, sock))
        else:
            from twisted.internet.threads import deferToThread
            d = deferToThread(self.threadedThing, sock, addr)
            d.addCallback(self.threadedDone)
            d.addErrback(self.threadedErr)

    def threadedThing(self, sock, addr):
        res = sock.connect_ex(addr)
        if res:
            raise error.getConnectError((res, os.strerror(res)))

## Define custom xxxOp classes to handle IO operations related
## to stdout/err/in for the process transport.
class ReadOutOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer)):
        if ret or not bytes:
            try:
                self.transport.outConnectionLost()
            except Exception, e:
                log.err(e)
                # Close all handles and proceed as normal,
                # waiting for process to exit.
                self.transport.closeStdout()
                self.transport.closeStderr()
                self.transport.closeStdin()
        else:
            try:
                self.transport.protocol.outReceived(buffer[:bytes])
            except Exception, e:
                log.err(e)
                # Close all handles and proceed as normal,
                # waiting for process to exit.
                self.transport.closeStdout()
                self.transport.closeStderr()
                self.transport.closeStdin()
            # Keep reading
            try:
                self.initiateOp(handle, buffer)
            except WindowsError, e:
                if e.errno in (ERROR_INVALID_HANDLE, ERROR_PIPE_ENDED):
                    self.transport.outConnectionLost()
                else:
                    raise e

    def initiateOp(self, handle, buffer):
        self.reactor.issueReadFile(handle, buffer, self.ovDone, (handle, buffer))

class ReadErrOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer)):
        if ret or not bytes:
            try:
                self.transport.errConnectionLost()
            except Exception, e:
                log.err(e)
                # Close all handles and proceed as normal,
                # waiting for process to exit.
                self.transport.closeStdout()
                self.transport.closeStderr()
                self.transport.closeStdin()
        else:
            try:
                self.transport.protocol.errReceived(buffer[:bytes])
            except Exception, e:
                log.err(e)
                # Close all handles and proceed as normal,
                # waiting for process to exit.
                self.transport.closeStdout()
                self.transport.closeStderr()
                self.transport.closeStdin()
            # Keep reading
            try:
                self.initiateOp(handle, buffer)
            except WindowsError, e:
                if e.errno in (ERROR_INVALID_HANDLE, ERROR_PIPE_ENDED):
                    self.transport.errConnectionLost()
                else:
                    raise e

    def initiateOp(self, handle, buffer):
        self.reactor.issueReadFile(handle, buffer, self.ovDone, (handle, buffer))

class WriteInOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer)):
        if ret or not bytes:
            try:
                self.transport.inConnectionLost()
            except Exception, e:
                log.err(e)
                # Close all handles and proceed as normal,
                # waiting for process to exit.
                self.transport.closeStdout()
                self.transport.closeStderr()
                self.transport.closeStdin()
        else:
            try:
                self.transport.writeDone(bytes)
            except Exception, e:
                log.err(e)
                # Close all handles and proceed as normal,
                # waiting for process to exit.
                self.transport.closeStdout()
                self.transport.closeStderr()
                self.transport.closeStdin()

    def initiateOp(self, handle, buffer):
        self.reactor.issueWriteFile(handle, buffer, self.ovDone, (handle, buffer))

class ReadInOp(OverlappedOp):
    """Stdin pipe will be opened in duplex mode.  The parent will read
    stdin to detect when the child closes it so we can close our end.
    """
    def ovDone(self, ret, bytes, (handle, buffer)):
        if ret or not bytes:
            self.transport.inConnectionLost()
        else:
            # Keep reading
            try:
                self.initiateOp(handle, buffer)
            except WindowsError, e:
                if e.errno in (ERROR_INVALID_HANDLE, ERROR_PIPE_ENDED):
                    self.transport.inConnectionLost()
                else:
                    raise e
                    
    def initiateOp(self, handle, buffer):
        self.reactor.issueReadFile(handle, buffer, self.ovDone, (handle, buffer))
