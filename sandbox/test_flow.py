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

from __future__ import generators
from flow import *
import unittest

class FlowTest(unittest.TestCase):
    
    
    def skip_testFlowConnect(self):
        from twisted.enterprise.adbapi import ConnectionPool
        pool = ConnectionPool("mx.ODBC.EasySoft","<some dsn>")
        def printResult(x): print x
        def printDone(): print "done"
        sql = "<some query>"
        f = Flow()
        f.waitInterval = 1
        f.addBranch(FlowQueryIterator(pool,sql),onFinish=printDone)
        f.addCallable(printResult)
        f.execute()

def testFlowIterator():
    class CountIterator(FlowIterator):
        def next(self): # this is run in a separate thread
            print "."
            from time import sleep
            sleep(.5)
            val = self.data
            if not(val):
                print "done counting"
                raise StopIteration
            self.data -= 1
            return [val]
    def printResult(data): print data
    def finished(): print "finished"
    f = Flow()
    f.addBranch(CountIterator, onFinish=finished)
    f.addCallable(printResult)
    f.waitInterval = 1
    f.execute(5)

def testFlow():
    '''
       primary tests of the Flow construct
    '''
    def printResult(data): print data
    def addOne(data): return  data+1
    def finished(): print "finished"
    def dataSource(data):  return [1, 1+data, 1+data*2]
    a = Flow()
    a.execute()
    a.addBranch(dataSource, finished)
    a.addCallable(addOne)
    a.addCallable(printResult)
    #a.execute(2)

    class simpleIterator:
        def __init__(self, data): 
            self.data = data
        def __iter__(self): 
            return self
        def next(self): 
            if self.data < 0: raise StopIteration
            ret = self.data
            self.data -= 1
            if ret % 2: 
                raise PauseFlow
            return ret

    def simpleGenerator(data):
        for x in [1,2,3,4,5,6]:
            if x % 2: raise PauseFlow
            yield x

    b = Flow()
    b.addBranch(simpleGenerator)
    b.addCallable(printResult)
    b.execute(5)

    class simpleIterator:
        def __init__(self, data): 
            self.data = data
        def __iter__(self): 
            return self
        def next(self): 
            print "."
            if self.data < 0: raise StopIteration
            ret = self.data
            self.data -= 1
            if ret % 2: 
                raise PauseFlow
            return ret
    
    c = Flow()
    c.addBranch(simpleIterator)
    c.addCallable(printResult)
    #c.execute(5)

    import operator
    d = Flow()
    d.addBranch(simpleIterator)
    d.addMerge(operator.add, 0)
    d.addCallable(printResult)

    e = Flow()
    e.addChain(a,d)
    #e.execute(3)

if '__main__' == __name__:
    testFlow()
    #testFlowIterator()
    from twisted.internet import reactor
    reactor.callLater(5,reactor.stop)
    reactor.run()
