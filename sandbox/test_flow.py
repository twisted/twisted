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

from __future__ import nested_scopes
import flow
import unittest

class producer:
    """ iterator version of the following generator... 

    def producer():
        lst = flow.Generator([1,2,3])
        nam = flow.Generator(['one','two','three'])
        while 1: 
            yield lst; yield nam
            if lst.stop or nam.stop:
                return
            yield (lst.result, nam.result)
    """
    def __iter__(self):
        self.lst   = flow.Generator([1,2,3])
        self.nam   = flow.Generator(['one','two','three'])
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
        title = flow.Generator(['Title'])
        lst = flow.Generator(producer())
        yield title
        yield title.getResult()
        try:
            while 1:
                yield lst
                yield lst.getResult()
        except flow.StopIteration: pass
    """    
    def __iter__(self):
        self.title = flow.Generator(['Title'])
        self.lst   = flow.Generator(producer())
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

class FlowTest(unittest.TestCase):
    def testBasic(self):
        f = flow.Flow([1,2,3])
        f.execute()
        self.assertEqual([1,2,3],f.results)

    def testProducer(self):
        f = flow.Flow(producer())
        f.execute() 
        self.assertEqual([(1,'one'),(2,'two'),(3,'three')],f.results)

    def testConsumer(self):
        f = flow.Flow(consumer())
        f.execute() 
        self.assertEqual(['Title',(1,'one'),(2,'two'),(3,'three')],f.results)

    def testDeferred(self):
        from twisted.internet import reactor
        def res(x):
            self.assertEqual(['Title', (1,'one'),(2,'two'),(3,'three')], x)
        f = flow.DeferredFlow(consumer())
        f.addCallback(res)
        reactor.iterate()

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
        def res(x): self.assertEqual([5,4,3,2,1], x)
        from twisted.internet import reactor
        f = flow.DeferredFlow(CountIterator(5))
        f.addCallback(res)
        reactor.callLater(2,reactor.stop)
        reactor.run()

if '__main__' == __name__:
    unittest.main()

