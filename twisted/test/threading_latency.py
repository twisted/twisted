"""Measure latency of reactor thread APIs. run with runtests."""

from pyunit import unittest
import time

from twisted.internet import reactor, threads


class LatencyTestCase(unittest.TestCase):

    numRounds = 5
    
    def setUp(self):
        self.from_times = []
        self.in_times = []
    
    def tearDown(self):
        threads.shutdown()
    
    def wait(self):
        start = time.time()
        while time.time() - start < 1:
            reactor.iterate(1.0)

    def printResult(self):
        print
        print
        print "callFromThread latency:"
        sum = 0
        for t in self.from_times: sum += t
        print "%f millisecond" % ((sum / self.numRounds) * 1000)

        print "callInThread latency:"
        sum = 0
        for t in self.in_times: sum += t
        print "%f millisecond" % ((sum / self.numRounds) * 1000)
        print
        print
    
    def testCallFromThread(self):
        for i in range(self.numRounds):
            reactor.callInThread(self.tcmf_2, time.time())
            self.wait()
        assert len(self.in_times) == len(self.from_times)
        assert len(self.in_times) == self.numRounds
        self.printResult()
    
    def tcmf_2(self, start):
        # runs in thread
        self.in_times.append(time.time() - start)
        reactor.callFromThread(self.tcmf_3, time.time())

    def tcmf_3(self, start):
        self.from_times.append(time.time() - start)
