# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Test methods in twisted.internet.threads and reactor thread APIs."""

from pyunit import unittest

from twisted.internet import threads, reactor
from twisted.python import threadable, failure

# make sure thread pool is shutdown
import atexit
atexit.register(reactor.suggestThreadPoolSize, 0)


class Counter:    
    index = 0
    
    def sync_add(self):
        """A thread-safe method."""
        self.add()

    def add(self):
        """A none thread-safe method."""
        next = self.index + 1
        if next != self.index + 1:
            raise ValueError
        self.index = next
    
    synchronized = ["sync_add"]

threadable.synchronize(Counter)


class ThreadsTestCase(unittest.TestCase):
    """Test twisted.internet.threads."""

    def testCallInThread(self):
        c = Counter()
        
        for i in range(1000):
            reactor.callInThread(c.sync_add)
        
        oldIndex = 0
        while c.index < 1000:
            assert oldIndex <= c.index
            oldIndex = c.index
        
        self.assertEquals(c.index, 1000)

    def testCallMultiple(self):
        c = Counter()
        # we call the non-thread safe method, but because they should
        # all be called in same thread, this is ok.
        commands = [(c.add, (), {})] * 1000
        threads.callMultipleInThread(commands)

        oldIndex = 0
        while c.index < 1000:
            assert oldIndex <= c.index
            oldIndex = c.index
        
        self.assertEquals(c.index, 1000)
    
    def testSuggestThreadPoolSize(self):
        reactor.suggestThreadPoolSize(34)
        reactor.suggestThreadPoolSize(4)

    gotResult = 0
    
    def testDeferredResult(self):
        d = threads.deferToThread(lambda x, y=5: x + y, 3, y=4)
        d.addCallback(self._resultCallback)
        while not self.gotResult:
            reactor.iterate()
        self.gotResult = 0

    def _resultCallback(self, result):
        self.assertEquals(result, 7)
        self.gotResult = 1

    def testDeferredFailure(self):
        def raiseError(): raise TypeError
        d = threads.deferToThread(raiseError)
        d.addErrback(self._resultErrback)
        while not self.gotResult:
            reactor.iterate()
        self.gotResult = 0

    def _resultErrback(self, error):
        self.assert_( isinstance(error, failure.Failure) )
        self.assertEquals(error.type, TypeError)
        self.gotResult = 1


