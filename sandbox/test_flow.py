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

from twisted.python.flow import *
from twisted.trial import unittest

class FlowTests(unittest.TestCase):
    def skip_testFlow(self):
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
        a.addFunction(addOne)
        a.addFunction(printResult)
        a.execute(2)
        
        class simpleIterator:
            def __init__(self, data): 
                self.data = data
            def __iter__(self): 
                return self
            def next(self): 
                if self.data < 0: raise StopIteration
                ret = self.data
                self.data -= 1
                return ret
        import operator
        b = Flow()
        b.addBranch(simpleIterator)
        b.addMerge(operator.add, 0)
        b.addFunction(printResult)
      
        c = Flow()
        c.addChain(a,b)
        c.execute(3)
    
    def skip_testFlowIterator(self):
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
                return val
        def printResult(data): print data
        def finished(): print "finished"
        f = Flow()
        f.addBranch(CountIterator, onFinish=finished)
        f.addFunction(printResult)
        f.waitInterval = 1
        f.execute(5)
    
    def skip_testFlowConnect(self):
        from twisted.enterprise.adbapi import ConnectionPool
        pool = ConnectionPool("mx.ODBC.EasySoft","<some dsn>")
        def printResult(x): print x
        def printDone(): print "done"
        sql = "<some query>"
        f = Flow()
        f.waitInterval = 1
        f.addBranch(FlowQueryIterator(pool,sql),onFinish=printDone)
        f.addFunction(printResult)
        f.execute()

if '__main__' == __name__:
    test = FlowTests()
    test.skip_testFlow() 
