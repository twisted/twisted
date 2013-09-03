# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
POSIX implementation of local network interface enumeration.
"""

from __future__ import division, absolute_import

import sys, socket
from os import strerror

from socket import AF_INET, AF_INET6, inet_ntop

from cffi import FFI

from twisted.python.compat import nativeString



ffi = FFI()
ffi.cdef("""
    struct sockaddr {
         short int sa_family;
         ...;
    };

    struct ifaddrs {
        struct ifaddrs  *ifa_next;    /* Next item in list */
        char            *ifa_name;    /* Name of interface */
        struct sockaddr *ifa_addr;    /* Address of interface */
        ...;
    };

    typedef size_t socklen_t;

    int getifaddrs(struct ifaddrs **ifap);
    void freeifaddrs(struct ifaddrs *ifa);
    int getnameinfo(const struct sockaddr *sa, socklen_t salen, char *host,
        size_t hostlen, char *serv, size_t servlen, int flags);
    const char *gai_strerror(int errcode);

    static const int AF_INET;
    static const int AF_INET6;
    static const size_t NI_MAXHOST;
    static const int NI_NUMERICHOST;
    const int sockaddr_in_size;
    const int sockaddr_in6_size;
""")
lib = ffi.verify("""
    #include <sys/types.h>
    #include <ifaddrs.h>
    #include <sys/socket.h>
    #include <netdb.h>

    const int sockaddr_in_size = sizeof(struct sockaddr_in);
    const int sockaddr_in6_size = sizeof(struct sockaddr_in6);
""")



def _interfaces():
    """
    Call C{getifaddrs(3)} and return a list of tuples of interface name, address
    family, and human-readable address representing its results.
    """
    ifaddrs = ffi.new('struct ifaddrs **')
    err = lib.getifaddrs(ifaddrs)
    if err != 0:
        raise OSError(ffi.errno, strerror(ffi.errno))
    results = []
    try:
        ifa = ifaddrs[0]
        while ifa != ffi.NULL:
            if ifa.ifa_addr != ffi.NULL:
                family = ifa.ifa_addr.sa_family
                if family == lib.AF_INET:
                    salen = lib.sockaddr_in_size
                elif family == lib.AF_INET6:
                    salen = lib.sockaddr_in6_size
                else:
                    salen = None

                if salen is not None:
                    addr = ffi.new('char[]', lib.NI_MAXHOST)
                    err = lib.getnameinfo(
                        ifa.ifa_addr, salen, addr, len(addr), ffi.NULL, 0,
                        lib.NI_NUMERICHOST)
                    if err != 0:
                        raise OSError(err, ffi.string(lib.gai_strerror(err)))
                    results.append((
                        ffi.string(ifa.ifa_name),
                        family,
                        ffi.string(addr)))
            ifa = ifa.ifa_next
    finally:
        lib.freeifaddrs(ifaddrs[0])
    return results



def posixGetLinkLocalIPv6Addresses():
    """
    Return a list of strings in colon-hex format representing all the link local
    IPv6 addresses available on the system, as reported by I{getifaddrs(3)}.
    """
    retList = []
    for (interface, family, address) in _interfaces():
        address = nativeString(address)
        if family == lib.AF_INET6 and address.startswith(b'fe80:'):
            retList.append(address)
    return retList
