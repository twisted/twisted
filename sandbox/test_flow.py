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
#
#
# to run test, use 'trial test_flow.py'
#

from __future__ import nested_scopes
import flow
from twisted.trial import unittest
from twisted.python import failure

class producer:
    """ iterator version of the following generator... 

    def producer():
        lst = flow.Wrap([1,2,3])
        nam = flow.Wrap(['one','two','three'])
        while 1: 
            yield lst; yield nam
            if lst.stop or nam.stop:
                return
            yield (lst.result, nam.result)
    """
    def __iter__(self):
        self.lst   = flow.Wrap([1,2,3])
        self.nam   = flow.Wrap(['one','two','three'])
        self.state = self.yield_lst
        return self
    def yield_lst(self):
        self.state = self.yield_nam
        return self.lst
    def yield_nam(self):
        self.state = self.yield_results
        return self.nam
    def yield_results(self):
        self.state = self.yield_lst
        if self.lst.stop or self.nam.stop:
            raise flow.StopIteration
        return (self.lst.result, self.nam.result)
    def next(self):
        return self.state()

class consumer:
    """ iterator version of the following generator...

    def consumer():
        title = flow.Wrap(['Title'])
        lst = flow.Wrap(producer())
        yield title
        yield title.getResult()
        try:
            while 1:
                yield lst
                yield lst.getResult()
        except flow.StopIteration: pass
    """    
    def __iter__(self):
        self.title = flow.Wrap(['Title'])
        self.lst   = flow.Wrap(producer())
        self.state = self.yield_title
        return self
    def yield_title(self):
        self.state = self.yield_title_result
        return self.title
    def yield_title_result(self):
        self.state = self.yield_lst
        return self.title.getResult()
    def yield_lst(self):
        self.state = self.yield_result
        return self.lst
    def yield_result(self):
        self.state = self.yield_lst
        return self.lst.getResult()
    def next(self):
        return self.state()

class badgen:
    """ a bad generator...

    def badgen():
        yield 'x'
        err =  3/ 0
    """    
    def __iter__(self):
        self.state = self.yield_x
        return self
    def yield_x(self):
        self.state = self.yield_done
        return 'x'
    def yield_done(self):
        err = 3 / 0
        raise StopIteration
    def next(self):
        return self.state()

def toList(it):
    from twisted.python.compat import iter, StopIteration
    ret = []
    it = iter(it)
    try:
       while 1:
           ret.append(it.next())
    except StopIteration: pass
    return ret         

class FlowTest(unittest.TestCase):
    def testBasic(self):
        lhs = [1,2,3]
        rhs = toList(flow.Iterator([1,2,3]))
        self.assertEqual(lhs,rhs)

    def testProducer(self):
        lhs = [(1,'one'),(2,'two'),(3,'three')]
        rhs = toList(flow.Iterator(producer()))
        self.assertEqual(lhs,rhs)

    def testConsumer(self):
        lhs = ['Title',(1,'one'),(2,'two'),(3,'three')]
        rhs = toList(flow.Iterator(consumer()))
        self.assertEqual(lhs,rhs)

    def testMerge(self):
        lhs = [1,'a',2,'b','c',3]
        mrg = flow.Merge([1,2,flow.Cooperate(),3],['a','b','c'])
        rhs = toList(flow.Iterator(mrg))
        self.assertEqual(lhs,rhs)

    def testDeferred(self):
        lhs = ['Title', (1,'one'),(2,'two'),(3,'three')]
        d = flow.Deferred(consumer())
        self.assertEquals(lhs, unittest.deferredResult(d))

    def testFailure(self):
        #
        # By default, the first time an error is encountered, it is
        # wrapped as a Failure and send to the errback
        #
        #    Failure(ZeroDivisionError)
        #
        d = flow.Deferred(badgen())
        r = unittest.deferredError(d) 
        self.failUnless(isinstance(r, failure.Failure))
        self.failUnless(isinstance(r.value, ZeroDivisionError))

    def testFailureAsResult(self):
        #
        # If failures are to be expected, then they can be
        # returned in the list of results.
        #
        #
        #   ['x',Failure(ZeroDivisionError)]
        #
        d = flow.Deferred(badgen(), failureAsResult = 1)
        r = unittest.deferredResult(d)
        self.assertEqual(len(r),2)   
        self.assertEqual(r[0],'x')   
        self.failUnless(isinstance(r[1], failure.Failure))
        self.failUnless(isinstance(r[1].value,ZeroDivisionError))

    def testThreaded(self):
        class CountIterator(flow.ThreadedIterator):
            def __init__(self, count):
                flow.ThreadedIterator.__init__(self)
                self.count = count
            def next(self): # this is run in a separate thread
                from time import sleep
                sleep(.1)
                val = self.count
                if not(val):
                    raise flow.StopIteration
                self.count -= 1
                return val
        d = flow.Deferred(CountIterator(5))
        self.assertEquals(unittest.deferredResult(d),[5,4,3,2,1])
