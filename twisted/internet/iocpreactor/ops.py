import struct, socket, os, errno
#import time

from twisted.python import failure

from _iocp import have_connectex
import error

SO_UPDATE_ACCEPT_CONTEXT = 0x700B
SO_UPDATE_CONNECT_CONTEXT = 0x7010

ERROR_CONNECTION_REFUSED = 1225
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
        if ret == 64: # ERROR_NETNAME_DELETED
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
            print "ConnectExOp err", ret
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

