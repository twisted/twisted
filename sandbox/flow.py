# Twisted, the Framework of Your Internet
# Copyright (C) 2003  Matthew W. Lefkowitz, Clark C. Evans
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General
# Public License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307
# USA

""" A resumable execution flow mechanism.

    Within single-threaded twisted main-loop, all code shares the same
    execution stack.  Sometimes it is useful when writing a handler
    to allow the handler to return (for example, if must block), but 
    saving the handler's state so it can be resumed later. 
"""

from __future__ import nested_scopes

class Flow:
    '''
       This object maintains a sequence of FlowStages which can be
       executed in order, where the output of one flow stage becomes
       the input of the next.   A flow starts with a top-level FlowStage,
       usually a producer of some sort, perhaps a database query, 
       followed by other filter stages until the data passed is 
       eventually consumed and None is returned.
   '''
    def __init__(self):
        '''
           Initializes a Flow object.  Processing starts at initialStage
           and then proceeds recursively.  Note that the stages are 
           recorded here as a StageItem singly-linked list.
        '''
        self.stageHead    = None
        self.stageTail    = None
        self.waitInterval = 0
    #     
    def append(self, stage):
        '''
            This appends an additional stage to the singly-linked
            list, starting with stageHead.
        '''
        link = FlowItem(stage)
        if not self.stageHead:
            self.stageHead = link
            self.stageTail = link
        else:
            self.stageTail.next = link
            self.stageTail = link
        return self

    def addFunction(self, callable, stop=None):
        self.append(FlowFunction(callable, stop))

    def addSequence(self, callable, onFinish = None):
        self.append(FlowSequence(callable, onFinish))

    def addContext(self, onFlush = None):
        self.append(FlowContext(onFlush))

    def addAccumulator(self, accum, start = None, 
                       finish = None, bucket = None):
        self.append(FlowAccumulator(accum, start, finish, bucket))

    def addDiscard(self):
        self.append(FlowStage())
    
    def execute(self, data = None):
        '''
           This executes the current flow, given empty
           starting data and the default initial state.
        '''
        if self.stageHead:
            stack = FlowStack(self.stageHead, data, self.waitInterval)
            stack.execute()

class FlowStack:
    '''
       a stack of FlowStages and a means for their execution
    '''
    def __init__(self, flowitem, data = None, waitInterval = 0):
        '''
           bootstraps the processing of the flow:

             flowitem      the very first stage in the process
             data          starting argument
             waitInterval  a useful item to slow the flow
        '''
        self._waitInterval = waitInterval
        self._stack   = []
        self._context = []  # see FlowContext
        self._stack.append((data, flowitem.stage, flowitem.next))
    #
    def context(self):
        cntx = self._context
        if cntx: 
            return cntx[-1]
    # 
    def push(self, data, stage=None, next=None):
        '''
           pushes a function to be executed onto the stack:
           
             data    argument to be passed
             stage   callable to be executed
             next    a FlowItem for subsequent stages
        '''
        if not stage:
            # assume the next stage in the process
            curr = self._current[2]
            if curr:
                stage = curr.stage
                next  = curr.next
        elif not next:
            # assume same stage, different function
            next = self._current[2]
        self._stack.append((data, stage, next))
    #
    def execute(self):
        '''
           This executes the current flow.
        '''
        stack = self._stack
        while stack:
            self._current = stack.pop()
            (data, stage, next) = self._current
            if not(stage): raise "unconsumed data"
            try:
                stage(self, data)
            except PauseFlow:
                self.push(data, stage, next)
                reactor.callLater(self._waitInterval,self.execute)
                return


class PauseFlow(Exception):
   '''
      This exception is used to pause a Flow, returning control
      back to the main event loop.  The flow automatically 
      reschedules itself to resume execution, resuming at the
      stage where it left off.
  '''

class FlowStage:
    ''' 
        operational unit in a flow, performs some sort of operation
        and optionally pushes other stages onto the call stack
    '''
    # 
    def __call__(self, flow, data):
        '''
            this is the minimum flow stage, it simply returns None,
            and thus indicates that the current branch is complete
        '''
        pass
 
class FlowFunction(FlowStage):
    ''' 
        wraps a function takign an input and returning a result; 
        in effect this implements one-to-one behavior
    '''
    def __init__(self, callable, stop = None):
        self.callable  = callable
        self.stop      = stop
    # 
    def __call__(self, flow, data):
        '''
            executes the callable and passes this data onto the next 
            stage in the flow; since this only pushes one item on
            to the stack, it is tail-recursive
        '''
        ret = self.callable(data)
        if ret is not self.stop:
            flow.push(ret)

class _FlowContext:
    '''
        innerds of the flow context, this object is created
        for each descend of a FlowContext stage, and has 
        attached callbacks.

        addOnFlush   adds a function to be called, optionally
                     with the 'context' attribute
    '''
    def __init__(self):
        self._flush = []
    #
    def addFlush(self, onFlush, bucket = None):
        args = onFlush.func_code.co_argcount
        if 0 == args: 
           fnc = lambda flow, cntx: onFlush()
        elif 1 == args:
           fnc = lambda flow, cntx: onFlush(getattr(cntx,bucket,None))
        else:
           fnc = onFlush
        self._flush.append(fnc)
   
class FlowContext(FlowStage):
    ''' 
        represents a branch of execution which may hold accumulated
        results and may have 'flush' handlers attached, which fire
        when the context is closed
    '''
    def __init__(self, onFlush = None):
        self.onFlush = onFlush

    def __call__(self, flow, data):
        ''' 
            adds the _FlowContext to the FlowStack's _context stack
        '''
        cntx = _FlowContext()
        if self.onFlush: 
            cntx.addFlush(self.onFlush)
        flow._context.append(cntx)
        flow.push(cntx, self.flush)
        flow.push(data)

    def flush(self, flow, cntx):
        '''
           cleans up the context and fires onFlush events
        '''
        top = flow._context.pop()
        assert top is cntx
        fncs = cntx._flush
        while fncs: flow.push(cntx, fncs.pop())


class FlowSequence(FlowStage):
    '''
        allows callable objects returning an iterator to be used
        within the system; this implements one-to-many behavior
    '''
    def __init__(self, callable, onFinish = None):
        self.callable = callable
        self.onFinish = onFinish
    # 
    def __call__(self, flow, data):
        '''
            executes the callable, and if an iterator object 
            is returned, schedules its next method
        '''
        ret = self.callable(data)
        if ret is not None:
            next = iter(ret).next
            flow.push(next, self.iterate)
    #
    def iterate(self, flow, next):
        '''
            if the next method has results, then schedule the
            next stage of the flow, otherwise finish up
        '''
        try:
            data = next()
            flow.push(next, self.iterate)
            flow.push(data)
        except StopIteration:
            if self.onFinish:
               self.onFinish()

class FlowAccumulator(FlowStage):
    '''
        the opposite of a FlowSequence, this takes multiple calls
        and converges them into a single call; this implements
        many-to-one behavior;  for the accumulator to work, it
        requires a FlowContext be higher up the call stack
    '''
    def __init__(self, accum, start = None, finish = None, bucket = None):
        if not bucket: bucket = id(self)
        self.bucket = str(bucket)
        self.start  = start
        self.accum  = accum
        self.finish = finish
    #
    def __call__(self, flow, data):
        '''
            executes the accum function
        '''
        cntx = flow.context()
        assert cntx, "FlowAccumulator needs a prior FlowContext"
        if not hasattr(cntx, self.bucket):
             if self.finish: cntx.addFlush(self.finish, self.bucket)
             acc = self.start
             if callable(acc): acc = acc()
        else:
             acc = getattr(cntx, self.bucket)
        acc = self.accum(acc, data)
        setattr(cntx, self.bucket, acc)

class FlowItem:
    '''
       a Flow is implemented as a series of FlowStage objects
       in a linked-list; this is the link node
        
         stage   a FlowStage in the linked list
         next    next FlowStageLink in this list
 
    '''
    def __init__(self,stage):
        self.stage = stage
        self.next  = None

class FlowIterator:
    '''
       This is an iterator base class which can be used to build
       iterators which are constructed and run within a Flow
    '''
    #
    def __init__(self, data = None):
        from twisted.internet.reactor import callInThread
        self.data = data  
        tunnel = _TunnelIterator(self)
        callInThread(tunnel.process)
        self._tunnel = tunnel
    #
    def __iter__(self): 
        return self._tunnel
    #
    def next(self):
        ''' 
            The method used to fetch the next value
        '''
        raise StopIteration

class _TunnelIterator:
    '''
       This is an iterator which tunnels output from an iterator
       executed in a thread to the main thread.   Note, unlike
       regular iterators, this one throws a PauseFlow exception
       which must be handled by calling reactor.callLater so that
       the producer threads can have a chance to send events to 
       the main thread.
    '''
    def __init__(self, source):
        '''
            This is the setup, the source argument is the iterator
            being wrapped, which exists in another thread.
        '''
        self.source     = source
        self.isFinished = 0
        self.failure    = None
        self.buff       = []
        self.append     = self.buff.append
    #
    def process(self):
        '''
            This is called in the 'source' thread, and 
            just basically sucks the iterator, appending
            items back to the main thread.
        '''
        from twisted.internet.reactor import callFromThread
        try:
            while 1:
                val = self.source.next()
                callFromThread(self.append,val)
        except StopIteration:
            callFromThread(self.stop)
        except Exception, e:
            print str(e)
            #failure = failure.Failure()
            #print "failing", failure
            #callFromThread(self.setFailure,failure)
    #
    def setFailure(self, failure):
        self.failure = failure
    #
    def stop(self):
        self.isFinished = 1
    #
    def next(self):
        if self.buff:
           return self.buff.pop(0)
        if self.isFinished:  
            raise StopIteration
        if self.failure:
            raise self.failure
        raise PauseFlow


class FlowQueryIterator(FlowIterator):
    def __init__(self, pool, sql):
        FlowIterator.__init__(self)
        self.curs = None
        self.sql  = sql
        self.pool = pool
        self.data = None
    def __call__(self,data):
        ret = FlowIterator.__call__(self,data)
        ret.append = ret.buff.extend
        return ret
    def next(self):
        if not self.curs:
            conn = self.pool.connect()
            self.curs = conn.cursor()
            if self.data: self.curs.execute(self.sql % self.data) 
            else: self.curs.execute(self.sql)
        res = self.curs.fetchone() # TODO: change to fetchmany
        if not(res): 
            self.curs.close()
            raise StopIteration
        return res

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
            return val
    def printResult(data): print data
    def finished(): print "finished"
    f = Flow()
    f.addSequence(CountIterator, onFinish=finished)
    f.addFunction(printResult)
    f.waitInterval = 1
    f.execute(5)

def testFlow():
    '''
       primary tests of the Flow construct
    '''
    def addOne(data): return  data+1
    def printResult(data): print data
    def finished(): print "finished"
    def dataSource(data):  return [1, 1+data, 1+data*2]
    f = Flow()
    f.execute()
    f.addSequence(dataSource, finished)
    f.addFunction(addOne)
    f.addFunction(printResult)
    f.execute(2)
    f.execute(11)
    
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
    f = Flow()
    f.addContext(finished)
    f.addSequence(simpleIterator)
    f.addAccumulator(operator.add, 0, printResult)


def testFlowConnect():
    from twisted.enterprise.adbapi import ConnectionPool
    pool = ConnectionPool("mx.ODBC.EasySoft","PSICustomerProto")
    def printResult(x): print x
    def printDone(): print "done"
    sql = "SELECT caption from vw_date"
    f = Flow()
    f.waitInterval = 1
    f.addStage(FlowQueryIterator(pool,sql),onFinish=printDone)
    f.addStage(printResult)
    f.execute()

# support iterators for 2.1
try:
   StopIteration = StopIteration
   iter = iter
except:
   StopIteration = IndexError
   class _ListIterator:
       def __init__(self,lst):
           self.idx = 0
           if getattr(lst,'keys',None): lst = lst.keys()
           self.lst = lst
       def next(self):
           idx = self.idx
           self.idx += 1
           return self.lst[idx]
   def iter(lst): 
       if hasattr(lst,'__iter__'):
           return lst.__iter__()
       else:
           return _ListIterator(lst)

if '__main__' == __name__:
    from twisted.internet import reactor
    testFlow()
    testFlowIterator()
    #testFlowConnect()
    reactor.callLater(5,reactor.stop)
    reactor.run()
