import struct, socket

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
            m = getattr(self.transport, "readErr")
            m(ret, bytes)
        else:
            m = getattr(self.transport, "readDone")
            m(bytes)

    def initiateOp(self, handle, buffer):
        self.reactor.issueReadFile(handle, buffer, self.ovDone, (handle, buffer))

class WriteFileOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer)):
        if ret or not bytes:
            m = getattr(self.transport, "writeErr")
            m(ret, bytes)
        else:
            m = getattr(self.transport, "writeDone")
            m(bytes)

    def initiateOp(self, handle, buffer):
        self.reactor.issueWriteFile(handle, buffer, self.ovDone, (handle, buffer))

class AcceptExOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, buffer, acc_sock)):
        if ret:
            m = getattr(self.transport, "acceptErr")
            m(ret, bytes)
        else:
            m = getattr(self.transport, "acceptDone")
            acc_sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_ACCEPT_CONTEXT, struct.pack("I", handle))
            m(acc_sock, acc_sock.getpeername())

    def initiateOp(self, handle):
        max_addr, family, type, protocol = self.reactor.getsockinfo(handle)
        acc_sock = socket.socket(family, type, protocol)
        buffer = self.reactor.AllocateReadBuffer(max_addr*2 + 32)
        self.reactor.issueAcceptEx(handle, acc_sock.fileno(), self.ovDone, (handle, buffer, acc_sock), buffer)

class ConnectExOp(OverlappedOp):
    def ovDone(self, ret, bytes, (handle, sock)):
        if ret:
            m = getattr(self.transport, "acceptErr")
            m(ret, bytes)
        else:
            m = getattr(self.transport, "acceptDone")
            sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, "")
            m()

    def initiateOp(self, sock, addr):
        handle = sock.fileno()
        max_addr, family, type, protocol = self.reactor.getsockinfo(handle)
        self.reactor.issueConnectEx(handle, family, addr, self.ovDone, (handle, sock))

