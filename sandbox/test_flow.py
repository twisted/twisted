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

from flow import *
import unittest

class CountIterator:
    def __init__(self, data): 
        self.data = data
    def __iter__(self): 
        return self
    def next(self): 
        if self.data < 0: raise StopIteration
        ret = self.data
        self.data -= 1
        return ret

class FlowTest(unittest.TestCase):

    def testBasic(self):   
        result = []
        def write(data): result.append(data)
        def addOne(data): return  data+1
        f = Flow()
        f.addCallable(addOne)
        f.addCallable(write)
        f.execute(2)
        f.execute(11)
        self.assertEqual(result, [3,12])

    def testBranch(self):  
        result = []
        def dataSource(data):  return [1, 1+data, 1+data*2]
        f = Flow()
        f.addBranch(dataSource)
        f.addCallable(lambda data: data + 1)
        f.addCallable(lambda data: result.append(data))
        f.execute(2)
        self.assertEqual(result, [2,4,6])

    def testReduce(self):
        import operator
        result = []
        f = Flow()
        f.addBranch(lambda data: [1,1+data,1+data*2])
        f.addReduce(operator.add, 0)
        f.addCallable(lambda data: result.append(data))
        f.execute(1)
        f.execute(2)
        self.assertEqual(result,[6,9])

    def testBranchViaIterator(self):
        import operator
        result = []
        f = Flow()
        f.addBranch(CountIterator)
        f.addReduce(operator.add, 0)
        f.addCallable(lambda data: result.append(data))
        f.execute(0); f.execute(1); f.execute(2)
        f.execute(3); f.execute(4); f.execute(5)
        self.assertEqual(result,[0,1,3,6,10,15])

    def testReduceInplace(self):
        import operator
        result = []
        f = Flow()
        def myadd(aggregate, data): aggregate[0] += data 
        f.addBranch(CountIterator)
        f.addReduce(myadd, lambda: [0], inplace = 1 )
        f.addCallable(lambda data: result.append(data[0]))
        f.execute(0); f.execute(1); f.execute(2)
        f.execute(3); f.execute(4); f.execute(5)
        self.assertEqual(result,[0,1,3,6,10,15])

    def testMerge(self):
        result = []
        f = Flow()
        def mymerge(curr, data):
            if curr: return (None,"%s%s" % (curr, data))
            return (str(data),None)
        f.addBranch(CountIterator)
        f.addMerge(mymerge)
        f.addCallable(lambda data: result.append(data))
        f.execute(3);
        f.execute(4);
        self.assertEqual(result,['32','10','43','21','0'])
     
def testFlowConnect(self):
    from twisted.enterprise.adbapi import ConnectionPool
    pool = ConnectionPool("mx.ODBC.EasySoft","<some dsn>")
    def printResult(x): print x
    def printDone(): print "done"
    sql = "<some query>"
    f = Flow()
    f.waitInterval = 1
    f.addBranch(QueryIterator(pool,sql),onFinish=printDone)
    f.addCallable(printResult)
    f.execute()

def testIterator():
    class CountIterator(Iterator):
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


if '__main__' == __name__:
    unittest.main()
    #testIterator()
    #from twisted.internet import reactor
    #reactor.callLater(5,reactor.stop)
    #reactor.run()
