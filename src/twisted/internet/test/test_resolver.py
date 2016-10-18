# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IHostnameResolver} and their interactions with
reactor implementations.
"""

from __future__ import division, absolute_import

__metaclass__ = type

from collections import defaultdict

from socket import gaierror, EAI_NONAME, AF_INET, SOCK_STREAM, IPPROTO_TCP
from threading import local, Lock

from zope.interface import implementer

from twisted.internet.interfaces import IResolutionReceiver

from twisted.trial.unittest import (
    SynchronousTestCase as UnitTest
)
from twisted.python.failure import Failure
from twisted.logger import Logger

from twisted.python.threadpool import ThreadPool
from twisted._threads import createMemoryWorker, Team, LockWorker

from twisted.internet.address import IPv4Address
from twisted.internet._resolver import GAIResolver


class DeterministicThreadPool(ThreadPool):
    """
    Create a deterministic L{ThreadPool} object.
    """
    def __init__(self, team):
        """
        
        """
        self.min = 1
        self.max = 1
        self.name = None
        self.threads = []
        self._team = team


errorLogger = Logger()

def deterministicPool():
    """
    Create a deterministic threadpool.

    @return: 2-tuple of L{ThreadPool}, 0-argument C{work} callable; when
        C{work} is called, do the work.
    """
    worker, doer = createMemoryWorker()
    def logIt():
        failure = Failure()
        errorLogger.failure("thread call failed", failure)
    return (
        DeterministicThreadPool(Team(LockWorker(Lock(), local()),
                                     (lambda: worker), logIt)),
        doer
    )



def deterministicReactorThreads():
    """
    Create a deterministic L{IReactorThreads}
    """
    worker, doer = createMemoryWorker()
    class CFT(object):
        def callFromThread(self, f, *a, **k):
            worker.do(lambda: f(*a, **k))
    return CFT(), doer



class FakeAddrInfoGetter(object):
    """
    Test object implementing getaddrinfo.
    """

    def __init__(self):
        """
        Create a L{FakeAddrInfoGetter}.
        """
        self.calls = []
        self.results = defaultdict(list)


    def getaddrinfo(self, host, port, family=0, socktype=0, proto=0, flags=0):
        """
        Mock for getaddrinfo.
        """
        self.calls.append((host, port, family, socktype, proto, flags))
        results = self.results[host]
        if results:
            return results
        else:
            raise gaierror(EAI_NONAME,
                           'nodename nor servname provided, or not known')


    def addResultForHost(self, host,
                         sockaddr,
                         family=AF_INET,
                         socktype=SOCK_STREAM,
                         proto=IPPROTO_TCP,
                         canonname=b""):
        """
        Add a result for a given hostname.
        """
        self.results[host].append(
            (family, socktype, proto, canonname, sockaddr)
        )


@implementer(IResolutionReceiver)
class ResultHolder(object):
    """
    A resolution receiver which holds onto the results it received.
    """
    _started = False
    _ended = False

    def __init__(self, testCase):
        """
        Create a L{ResultHolder} with a L{UnitTest}.
        """
        self._testCase  = testCase


    def resolutionBegan(self, hostResolution):
        """
        Hostname resolution began.
        """
        self._started = True
        self._resolution = hostResolution
        self._addresses = []


    def addressResolved(self, address):
        """
        An address was resolved.
        """
        self._addresses.append(address)


    def resolutionComplete(self):
        """
        Hostname resolution is complete.
        """
        self._ended = True



class HostnameResolutionTest(UnitTest):
    """
    Tests for hostname resolution.
    """

    def test_resolveOneHost(self):
        """
        Resolve an individual host.
        """
        pool, worker = deterministicPool()
        reactor, reactwork = deterministicReactorThreads()
        getter = FakeAddrInfoGetter()
        receiver = ResultHolder(self)
        resolver = GAIResolver(reactor, pool, getter.getaddrinfo)
        getter.addResultForHost(b"sample.example.com", ("4.3.2.1", 0))

        resolution = resolver.resolveHostName(receiver, u"sample.example.com")
        self.assertIdentical(receiver._resolution, resolution)
        self.assertEqual(receiver._started, True)
        self.assertEqual(receiver._ended, False)
        worker()
        reactwork()
        self.assertEqual(receiver._ended, True)
        self.assertEqual(receiver._addresses,
                         [IPv4Address('TCP', '4.3.2.1', 0)])
