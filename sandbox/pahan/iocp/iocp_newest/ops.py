import struct, socket
from iocpcore import have_connectex

SO_UPDATE_ACCEPT_CONTEXT = 0x700B
SO_UPDATE_CONNECT_CONTEXT = 0x7010

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
        if ret or not bytes:
            self.transport.writeErr(ret, bytes)
        else:
            self.transport.writeDone(bytes)

    def initiateOp(self, handle, buffer):
        self.reactor.issueWriteFile(handle, buffer, self.ovDone, (handle, buffer))

class AcceptExOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer, acc_sock)):
        if ret:
            self.transport.acceptErr(ret, bytes)
        else:
            acc_sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_ACCEPT_CONTEXT, struct.pack("I", handle))
            self.transport.acceptDone(acc_sock, acc_sock.getpeername())

    def initiateOp(self, handle):
        max_addr, family, type, protocol = self.reactor.getsockinfo(handle)
        acc_sock = socket.socket(family, type, protocol)
        buffer = self.reactor.AllocateReadBuffer(max_addr*2 + 32)
        self.reactor.issueAcceptEx(handle, acc_sock.fileno(), self.ovDone, (handle, buffer, acc_sock), buffer)

class ConnectExOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, sock)): # change this signature
        if ret:
            self.transport.connectErr(ret, bytes)
        else:
            if have_connectex:
                sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, "")
            self.transport.connectDone()

    def initiateOp(self, sock, addr):
        handle = sock.fileno()
        if have_connectex:
            max_addr, family, type, protocol = self.reactor.getsockinfo(handle)
            self.reactor.issueConnectEx(handle, family, addr, self.ovDone, (handle, sock))
        else:
            from twisted.internet.threads import deferToThread
            from twisted.python import log
            d = deferToThread(self.threadedThing, sock, addr)
            d.addCallback(self.ovDone, None, (None, None))
            d.addErrback(log.err) # should not occur

    def threadedThing(self, sock, addr):
        res = sock.connect_ex(addr)
        return res

