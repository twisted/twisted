
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


"""
Test cases for timeoutqueue module.
"""
import threading, time

from twisted.trial import unittest
from twisted.python import timeoutqueue


class TimeoutQueueTest(unittest.TestCase):
    
    def setUp(self):
        self.q = timeoutqueue.TimeoutQueue()
    
    def tearDown(self):
        del self.q
    
    def put(self):
        time.sleep(1)
        self.q.put(1)
        
    def testTimeout(self):
        q = self.q

        try:
            q.wait(1)
        except timeoutqueue.TimedOut:
            pass
        else:
            raise AssertionError, "didn't time out"

    def testGet(self):
        q = self.q
        start = time.time()
        threading.Thread(target=self.put).start()
        q.wait(1.5)
        assert time.time() - start < 2

        result = q.get(0)
        if result != 1:
            raise AssertionError, "didn't get item we put in"


testCases = [TimeoutQueueTest]
