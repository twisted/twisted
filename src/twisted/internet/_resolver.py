# -*- test-case-name: twisted.internet.test.test_resolver -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
IPv6-aware hostname resolution.

@see: L{IHostnameResolver}
"""

from __future__ import division, absolute_import

__metaclass__ = type

from socket import getaddrinfo, AF_INET, AF_INET6

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


@implementer(IHostnameResolver)
class GAIResolver(object):
    """
    L{IHostnameResolver} implementation that resolves hostnames by calling
    L{getaddrinfo} in a thread.
    """

    def __init__(self, reactor, threadpool=None, getaddrinfo=getaddrinfo):
        """
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
        @see: L{IHostnameResolver.resolveHostName}
        """
        d = deferToThreadPool(self._reactor, self._threadpool,
                              self._getaddrinfo, hostName, portNumber)
        resolution = HostResolution(hostName)
        resolutionReceiver.resolutionBegan(resolution)
        @d.addCallback
        def deliverResults(result):
            for family, socktype, proto, cannoname, sockaddr in result:
                addrType = {AF_INET: IPv4Address,
                            AF_INET6: IPv6Address}[family]
                resolutionReceiver.addressResolved(
                    addrType('TCP', *sockaddr)
                )
            resolutionReceiver.resolutionComplete()
        return resolution
