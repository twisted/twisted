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

    def testSequence(self):  
        result = []
        def dataSource(data):  return [1, 1+data, 1+data*2]
        f = Flow()
        f.addSequence(dataSource)
        f.addCallable(lambda data: data + 1)
        f.addCallable(lambda data: result.append(data))
        f.execute(2)
        self.assertEqual(result, [2,4,6])

    def testReduce(self):
        import operator
        result = []
        f = Flow()
        f.addSequence(lambda data: [1,1+data,1+data*2])
        f.addReduce(operator.add, 0)
        f.addCallable(lambda data: result.append(data))
        f.execute(1)
        f.execute(2)
        self.assertEqual(result,[6,9])

    def testSequenceViaIterator(self):
        import operator
        result = []
        f = Flow()
        f.addSequence(CountIterator)
        f.addReduce(operator.add, 0)
        f.addCallable(lambda data: result.append(data))
        f.execute(0); f.execute(1); f.execute(2)
        f.execute(3); f.execute(4); f.execute(5)
        self.assertEqual(result,[0,1,3,6,10,15])

    def testReduceInplace(self):
        import operator
        result = []
        f = Flow()
        def myadd(aggregate, data): 
            aggregate[0] += data 
        f.addSequence(CountIterator)
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
        f.addSequence(CountIterator)
        f.addMerge(mymerge)
        f.addCallable(lambda data: result.append(data))
        f.execute(3);
        f.execute(4);
        self.assertEqual(result,['32','10','43','21','0'])
    
    def testNestedContext(self):
        import operator
        result = []
        f = Flow()
        f.addSequence(CountIterator)
        f.addContext()
        f.addSequence(CountIterator)
        f.addReduce(operator.add, 0)
        f.addCallable(lambda data: result.append(data))
        f.execute(2);
        self.assertEqual(result,[3,1,0])
         
    def testAccessContext(self):
        class dummy: pass
        dummy = dummy()
        dummy.increment = 3
        result = []
        f = Flow()
        f.addCallable(lambda cntx, data: data + cntx.increment)
        f.addCallable(lambda data: result.append(data))
        f.execute(2, dummy)
        self.assertEqual(result, [5])

    def testChain(self):
        result = []
        a = Flow()
        a.addCallable(lambda data: result.append(('a',data)))
        b = Flow()
        b.addCallable(lambda data: result.append(('b',data)))
        f = Flow()
        f.addChain(a,b)
        f.execute(3)
        self.assertEqual(result, [('a',3),('b',3)])

    def testChainContext(self):
        import operator
        result = []
        a = Flow()
        a.addSequence(CountIterator)
        a.addReduce(operator.add, 0)
        a.addCallable(lambda data: result.append(('a',data)))
        b = Flow()
        def middle(cntx, data):
            cntx.root.data = data
            result.append(('b','data'))
        b.addCallable(middle)
        c = Flow()
        c.addCallable(lambda: result.append("done"))
        d = Flow()
        d.addCallable(lambda cntx, data: result.append(cntx.root.data))
        f = Flow()
        f.addChain(a,b,c,d)
        f.execute(3)
        self.assertEqual(result, [('a',6),('b','data'), 'done', 3 ])

    def testThreaded(self):
        class CountIterator(ThreadedIterator):
            def next(self): # this is run in a separate thread
                from time import sleep
                sleep(.1)
                val = self.data
                if not(val):
                    raise StopIteration
                self.data -= 1
                return [val]
        result = []
        def finished(): result.append('Finished')
        f = TwistedFlow(.1)
        f.addSequence(CountIterator, onFinish=finished)
        f.addCallable(lambda data: result.append(data))
        f.execute(5)
        from twisted.internet import reactor
        reactor.callLater(1,reactor.stop)
        reactor.run()
        self.assertEqual(result, [5,4,3,2,1,'Finished'])

if '__main__' == __name__:
    unittest.main()
