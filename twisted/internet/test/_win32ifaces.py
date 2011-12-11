# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Windows implementation of local network interface enumeration.
"""

from socket import socket, AF_INET6, SOCK_STREAM
from ctypes import (
    WinDLL, byref, create_string_buffer, c_int, c_void_p,
    POINTER, Structure, cast, string_at)

SIO_ADDRESS_LIST_QUERY = 0x48000016
WSAEFAULT = 10014

class SOCKET_ADDRESS(Structure):
    _fields_ = [('lpSockaddr', c_void_p),
                ('iSockaddrLength', c_int)]



def make_SAL(ln):
    class SOCKET_ADDRESS_LIST(Structure):
        _fields_ = [('iAddressCount', c_int),
                    ('Address', SOCKET_ADDRESS * ln)]
    return SOCKET_ADDRESS_LIST



def win32GetLinkLocalIPv6Addresses():
    """
    Return a list of strings in colon-hex format representing all the link local
    IPv6 addresses available on the system, as reported by
    I{WSAIoctl}/C{SIO_ADDRESS_LIST_QUERY}.
    """
    ws2_32 = WinDLL('ws2_32')
    WSAIoctl = ws2_32.WSAIoctl
    WSAAddressToString = ws2_32.WSAAddressToStringA

    s = socket(AF_INET6, SOCK_STREAM)
    size = 4096
    retBytes = c_int()
    for i in range(2):
        buf = create_string_buffer(size)
        ret = WSAIoctl(
            s.fileno(),
            SIO_ADDRESS_LIST_QUERY, 0, 0, buf, size, byref(retBytes), 0, 0)

        # WSAIoctl might fail with WSAEFAULT, which means there was not enough
        # space in the buffer we have it.  There's no way to check the errno
        # until Python 2.6, so we don't even try. :/ Maybe if retBytes is still
        # 0 another error happened, though.
        if ret and retBytes.value:
            size = retBytes.value
        else:
            break

    # If it failed, then we'll just have to give up.  Still no way to see why.
    if ret:
        raise RuntimeError("WSAIoctl failure")

    addrList = cast(buf, POINTER(make_SAL(0)))
    addrCount = addrList[0].iAddressCount
    addrList = cast(buf, POINTER(make_SAL(addrCount)))

    # For some reason, the WSAAddressToString call doesn't succeed very often if
    # this buffer is smaller (eg, 1024 bytes).  It's not clear why this larger
    # buffer size fixes (or makes less frequent) the failure.
    buf2 = create_string_buffer(1024 * 16)

    retList = []
    for i in range(addrList[0].iAddressCount):
        retBytes.value = 1024
        addr = addrList[0].Address[i]
        ret = WSAAddressToString(
            addr.lpSockaddr, addr.iSockaddrLength, 0, buf2, byref(retBytes))
        if ret:
            raise RuntimeError("WSAAddressToString failure")
        retList.append(string_at(buf2))
    return [addr for addr in retList if '%' in addr]
