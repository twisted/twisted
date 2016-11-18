# -*- test-case-name: twisted.internet.test.test_resolver -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
IPv6-aware hostname resolution.

@see: L{IHostnameResolver}
"""

from __future__ import division, absolute_import

__metaclass__ = type

from socket import (getaddrinfo, AF_INET, AF_INET6, AF_UNSPEC, SOCK_STREAM,
                    SOCK_DGRAM, gaierror)

from zope.interface import implementer

from twisted.internet.interfaces import IHostnameResolver, IHostResolution
from twisted.internet.threads import deferToThreadPool
from twisted.internet.address import IPv4Address, IPv6Address


@implementer(IHostResolution)
class HostResolution(object):
    """
    The in-progress resolution of a given hostname.
    """

    def __init__(self, name):
        """
        Create a L{HostResolution} with the given name.
        """
        self.name = name



_any = frozenset([IPv4Address, IPv6Address])

_typesToAF = {
    frozenset([IPv4Address]): AF_INET,
    frozenset([IPv6Address]): AF_INET6,
    _any: AF_UNSPEC,
}

_afToType = {
    AF_INET: IPv4Address,
    AF_INET6: IPv6Address,
}

_transportToSocket = {
    'TCP': SOCK_STREAM,
    'UDP': SOCK_DGRAM,
}

_socktypeToType = {
    SOCK_STREAM: 'TCP',
    SOCK_DGRAM: 'UDP',
}



@implementer(IHostnameResolver)
class GAIResolver(object):
    """
    L{IHostnameResolver} implementation that resolves hostnames by calling
    L{getaddrinfo} in a thread.
    """

    def __init__(self, reactor, threadpool=None, getaddrinfo=getaddrinfo):
        """
        Create a L{GAIResolver}.

        @param reactor: the reactor to schedule result-delivery on
        @type reactor: L{IReactorThreads}

        @param threadpool: the thread pool to use for scheduling name
            resolutions.  If not supplied, the use the given C{reactor}'s
            thread pool.
        @type threadpool: L{twisted.internet.threads}

        @param getaddrinfo: a reference to the L{getaddrinfo} to use - mainly
            parameterized for testing.
        @type getaddrinfo: callable with the same signature as L{getaddrinfo}
        """
        self._reactor = reactor
        self._threadpool = threadpool
        self._getaddrinfo = getaddrinfo


    def resolveHostName(self, resolutionReceiver, hostName, portNumber=0,
                        addressTypes=None, transportSemantics='TCP'):
        """
        See L{IHostnameResolver.resolveHostName}

        @param resolutionReceiver: see interface

        @param hostName: see interface

        @param portNumber: see interface

        @param addressTypes: see interface

        @param transportSemantics: see interface

        @return: see interface
        """
        addressFamily = _typesToAF[_any if addressTypes is None
                                   else frozenset(addressTypes)]
        socketType = _transportToSocket[transportSemantics]
        def get():
            try:
                return self._getaddrinfo(hostName, portNumber, addressFamily,
                                         socketType)
            except gaierror:
                return []
        d = deferToThreadPool(self._reactor, self._threadpool, get)
        resolution = HostResolution(hostName)
        resolutionReceiver.resolutionBegan(resolution)
        @d.addCallback
        def deliverResults(result):
            for family, socktype, proto, cannoname, sockaddr in result:
                addrType = _afToType[family]
                resolutionReceiver.addressResolved(
                    addrType(_socktypeToType.get(socktype, 'TCP'), *sockaddr)
                )
            resolutionReceiver.resolutionComplete()
        return resolution
