# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import struct

from socket import AF_INET, AF_INET6, inet_pton, htons

from twisted.internet.iocpreactor import const
from twisted.internet.defer import Deferred

from ._iocp import ffi, lib

lib.initialize_function_pointers()

NULL = ffi.NULL


class Event(object):
    def __init__(self, callback, owner, **kw):
        self.callback = callback
        self.owner = owner
        for k, v in kw.items():
            setattr(self, k, v)

    def __repr__(self):
        return "<event cb={} owner={}>".format(self.callback, self.owner)


class CompletionPort(object):
    """
    An IOCP CompletionPort thing.
    """

    def __init__(self, reactor):

        self.reactor = reactor
        self.events = {}
        self.ports = []

        self.port = CreateIoCompletionPort(
            None, 0, 0, 0)


    def getEvent(self, timeout):
        status = GetQueuedCompletionStatus(self.port, timeout)
        status = list(status)

        if status[3] in self.events.keys():
            status[3] = self.events.pop(status[3])

        return status

    def postEvent(self, b, key, event):
        PostQueuedCompletionStatus(self.port, b, key, 0)

    def addHandle(self, handle, key):
        CreateIoCompletionPort(handle, self.port, key, 0)


def accept(listening, accepting, event):

    ov = Overlapped(0)
    res = ov.AcceptEx(listening, accepting)

    event.overlapped = ov
    event.owner.reactor.port.events[ov.address] = event
    event.port = ov

    return res


def connect(socket, address, event):

    ov = Overlapped(0)
    res = ov.ConnectEx(socket, address)

    event.overlapped = ov
    event.owner.reactor.port.events[ov.address] = event

    return res


def recv(socket, len, event, flags=0):

    ov = Overlapped(0)
    event.overlapped = ov
    event.owner.reactor.port.events[ov.address] = event

    try:
        res = ov.WSARecv(socket, len, flags)
    except OSError as e:
        res = e.winerror

    return res


def recvfrom(socket, length, event, flags=0):

    ov = Overlapped(0)
    event.overlapped = ov
    event.owner.reactor.port.events[ov.address] = event

    res = ov.WSARecvFrom(socket, length, flags)
    return res


def send(socket, data, event, flags=0):

    ov = Overlapped(0)
    event.overlapped = ov
    event.owner.reactor.port.events[ov.address] = event

    res = ov.WSASend(socket, data, flags)

    return res


def parse_address(socket, address):

    if socket.family == AF_INET:

        addr = ffi.new("struct sockaddr_in*")
        addr[0].sin_family = AF_INET
        addr[0].sin_port = htons(address[1])
        addr[0].sin_addr = inet_pton(AF_INET, address[0])

    elif socket.family == AF_INET6:

        addr = ffi.new("struct sockaddr_in6*")
        addr[0].sin6_family = AF_INET6
        addr[0].sin6_port = htons(address[1])
        addr[0].sin6_addr = inet_pton(AF_INET6, address[0])

    return addr

def GetQueuedCompletionStatus(port, timeout):

    key = ffi.new("ULONG_PTR*")
    b = ffi.new("DWORD*")
    ov = ffi.new("intptr_t*")

    rc = lib.GetQueuedCompletionStatus(port, b, key, ov, timeout)

    if not rc:
        rc = ffi.getwinerror()[0]
    else:
        rc = 0

    rval = (rc, b[0], key[0], int(ov[0]))

    return rval

def CreateIoCompletionPort(handle, port, key, concurrency):
    """
    returns a port
    """
    if isinstance(handle, int):
        h = handle
    else:
        h = lib.getInvalidHandle()

    a = lib.CreateIoCompletionPort(h, port, key, concurrency)

    if not a:
        raise Exception(ffi.getwinerror())

    return a

def PostQueuedCompletionStatus(port, bytes, key, whatever):
    o = Overlapped(0)
    a = lib.PostQueuedCompletionStatus(port, bytes, key, o._ov)

    if not a:
        raise Exception(ffi.getwinerror())

    return a


class Overlapped(object):

    def __init__(self, handle):
        assert handle == 0
        self._ov = ffi.new("OVERLAPPED*")
        self._buffer = None
        self._wsabuf = None
        self._handle = None


    def getresult(self, wait=False):
        f = ffi.buffer(self._buffer)
        return f

    def getRecvAddress(self):

        from socket import inet_ntop, ntohs

        if self._socketFamily == AF_INET:
            address = inet_ntop(AF_INET, ffi.buffer(self.recvAddress[0].sin_addr))
            port = ntohs(self.recvAddress[0].sin_port)

        elif self._socketFamily == AF_INET6:
            address = inet_ntop(AF_INET6, ffi.buffer(self.recvAddress[0].sin6_addr))
            port = ntohs(self.recvAddress[0].sin6_port)

        return (address, port)

    @property
    def address(self):

        addr = int(ffi.cast("intptr_t", self._ov))
        return addr


    def AcceptEx(self, listen, accept):

        self._handle = accept

        size = ffi.sizeof("struct sockaddr_in6") + 16

        buf = ffi.new("char* [" + str(size) + "]")
        recv = ffi.new("DWORD*")
        recvDesired = 0
        sizeOf = size

        res = lib.AcceptEx(
            listen.fileno(), accept.fileno(),
            buf,
            0, size, size, recv, self._ov
        )

        if not res:
            return ffi.getwinerror()[0]

        return res

    def ConnectEx(self, socket, address):

        self._handle = socket

        addr = parse_address(socket, address)
        length = ffi.sizeof(addr[0])

        if socket.family == AF_INET:
            func = lib.Tw_ConnectEx4
        elif socket.family == AF_INET6:
            func = lib.Tw_ConnectEx6

        res = func(
            socket.fileno(),
            addr,
            length,
            ffi.NULL, 0, ffi.NULL, self._ov
        )   

        if not res:
            return ffi.getwinerror()[0]

        return res

    def WSARecv(self, socket, length, flags=0):

        self._handle = socket

        wsabuf = ffi.new("WSABUF*")

        buff = ffi.new("char [" + str(length) + "]")

        wsabuf[0].len = length
        wsabuf[0].buf = ffi.addressof(buff)

        self._buffer = buff
        self._wsabuf = wsabuf

        read = ffi.new("DWORD*")
        
        _flags = ffi.new("DWORD*")
        _flags[0] = flags

        bufflen = ffi.new("DWORD*")
        bufflen[0] = 1

        res = lib.WSARecv(socket.fileno(), wsabuf, 1, read, _flags, self._ov, NULL)

        return ffi.getwinerror()[0], read[0]

    def WSARecvFrom(self, socket, length, flags=0):
    
        # int WSARecvFrom(HANDLE s, WSABUF *buffs, DWORD buffcount,
        # DWORD *bytes, DWORD *flags, sockaddr *fromaddr, int *fromlen,
        # OVERLAPPED *ov, void *crud)

        self._handle = socket

        wsabuf = ffi.new("WSABUF*")

        buff = ffi.new("char [" + str(length) + "]")

        wsabuf[0].len = length
        wsabuf[0].buf = ffi.addressof(buff)

        self._buffer = buff
        self._wsabuf = wsabuf

        read = ffi.new("DWORD*")
        
        _flags = ffi.new("DWORD*")
        _flags[0] = flags

        bufflen = ffi.new("DWORD*")
        bufflen[0] = 1

        if socket.family == AF_INET:
            recvAddress = ffi.new("struct sockaddr_in*")
        elif socket.family == AF_INET6:
            recvAddress = ffi.new("struct sockaddr_in6*")

        self._socketFamily = socket.family
        self.recvAddress = recvAddress

        recvAddress2 = ffi.cast("struct sockaddr*", recvAddress)
        recvAddressSize = ffi.new("int*", ffi.sizeof(recvAddress[0]))
        self.recvAddress2 = recvAddress2

        res = lib.WSARecvFrom(socket.fileno(), wsabuf, 1, read, _flags, recvAddress2,
            recvAddressSize, self._ov, NULL)

        return ffi.getwinerror()[0], read[0]


    def WSASend(self, socket, data, flags=0):

        self._handle = socket

        wsabuf = ffi.new("WSABUF*")

        buff = ffi.new("char [" + str(len(data)+1) + "]", data)

        wsabuf[0].len = len(data)
        wsabuf[0].buf = ffi.addressof(buff)

        self._buffer = buff
        self._wsabuf = wsabuf

        _flags = ffi.new("DWORD*")
        _flags[0] = flags

        bytesSent = ffi.new("DWORD*")

        res = lib.WSASend(socket, wsabuf, 1, bytesSent, flags, self._ov, NULL)

        return ffi.getwinerror()[0], bytesSent[0]
