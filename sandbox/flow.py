# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitz
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
#
#
# Changelog:
#   3/13/2003  Clark C. Evans    Initial Stable Version

""" A resumable execution flow mechanism.

    Within single-threaded twisted main-loop, all code shares the same
    execution stack.  Sometimes it is useful when writing a handler
    to allow the handler to return (for example, if must block), but 
    saving the handler state so it can be resumed later. 
"""
from twisted.python.reflect import getArgumentCount
from twisted.python.compat import StopIteration, iter
from __future__ import nested_scopes

class PauseFlow(Exception):
   """
      This exception is used to pause a Flow, returning control
      back to the main event loop.  The flow automatically 
      reschedules itself to resume execution, resuming at the
      stage where it left off.  This exception can be thrown
      inside of any stage, and that stage will be re-scheduled
      for another time.  This is useful when a resource needed
      to complete a stage is busy.   The entire reason for this
      library is to support complicated flows where this 
      exception can be raised.
  """
PauseFlowValue = PauseFlow()

class Flow:
    """ a sequence of Stages which can be executed more than once

       This object maintains a sequence of Stages which can be
       executed in order, where the output of one flow stage becomes
       the input of the next.   A flow starts with a top-level Stage,
       usually a producer of some sort, perhaps a database query, 
       followed by other filter stages until the data passed is 
       eventually consumed and None is returned.  The sequence is
       stored using a linked-list.
    """

    def addDiscard(self):
        """ the no-op stage """
        return self._append(Stage())

    def addCallable(self, callable, skip = None):
        """ wraps a function or other callable for use in a flow

            This wraps a callable with a single input parameter
            and an optional output value, one-to-one behavior.
            If the return value is skip (None if you do not have 
            a return statement) then the next stage is not processed.
             
            Note that this implementation is tail recursive, that is, 
            in most cases each callable finishes executing before the 
            next stage is pushed onto the stack.
        """
        return self._append(Callable(callable, skip))

    def addSequence(self, callable, onFinish = None):
        """ wraps an iterator; in effect one-to-many behavior

            This wraps an iterable object so that it can be used
            within a data flow.  This protocol has three stages:

                First, the callable is applied with a single argument,
                the data value from the parent data flow.   This can
                be a function returning a list, for example.  Or, it
                could be a class implementing the iterator protocol 
                with a __init__ taking a "data" argument.
 
                Second, the result value, if any, is passed to iter,
                where __iter__ is called to create an iterator.  This
                is just a step in the iterator protocol, but can be 
                useful under some circumstances.   If the result of 
                the first stage is a list or tuple, then this is 
                handled automatically.
 
                Third, the next() method of the returned object is
                executed repeatedly untill StopIteration is raised.
                For each time the next() function returns, its 
                result is passed onto the next stage.
            
            Optionally, an onFinish function can be provided which 
            is executed after the iteration finishes.  This function
            takes no arguments. 
        """            
        return self._append(Sequence(callable, onFinish))
    
    def addReduce(self, callable, start = None, inplace = 0):
        """ aggregates results; in effect many-to-one behavior

            This stage is the opposite of the Sequence stage, it accepts
            multiple calls and aggregates them into a single call.
    
                callable   the function or operator which will merge the 
                           output; the function has two paramaters, first
                           is the current accumulated value, and second is
                           the value passed via the stream; the output 
                           depends on the "inplace" parameter.
    
                start      the starting value; or, if it is a callable,
                           a function taking no arguments that will be
                           applied to create a starting value
    
                inplace    If inplace is true, then the result of the 
                           callable will not be used to set the 
                           accumulated value, otherwise the result of
                           the callable becomes the accumulated value
                           to be used in the next call
    
            Note that the stage uses the most nested Context for holding 
            the accumulation bucket; thus placement of Context stages 
            could be used to capture intermediate results, etc.
        """
        return self._append(Reduce(callable, start, inplace))

    def addReduceToList(self):
        """ accumulates events into a list """
        return self._append(Reduce())

    def addMerge(self, callable, start = None, skip = None):
        """ a more general reduce, resulting in more than one output

            This is a more general form of "reduce" where M messages
            may be merged into N messages (N < M).   To do this, the
            output may be delayed one call; thus, to know that the 
            stage is to produce a result, it may have to look at the
            next value.

            Thus, the callable for this function has two inputs
            (just like result); however, the output is a tuple
            containing two items, the accumulated value to be
            passed in the next call and the value (if any) to 
            send on to the next stage.   At the end of input,
            the accumulated value is then sent to the next stage.
        """
        return self._append(Merge(callable, start, skip))

    def addContext(self, onFlush = None):
        """ adds a nested context, provides for end notification

            In a flow, introducing a branch or a callable does not
            necessarly create a variable context.  This is done explicitly
            with this Stage.  This context also provides a callback
            which can be used with the context is flushed, that is when
            all child processes have finished.  
        """
        return self._append(Context(onFlush))

    def addFilter(self, callable, skip = None, rootContext = 0):
        """ a callable which takes a context for a first argument

            This is almost identical to Callback, only that it takes
            either a local or global context for the first argument
            and the data value for the second argument.
        """
        return self._append(Filter(callable, skip, rootContext))

    def addChain(self, *flows):
        """ adds one or more flows to the current flow

            In some cases it is necessary to daisy-chain flows
            together so that the stages from the chained flows
            are executed in the current flow context
        """
        return self._append(Chain(flows))
 
    def addConstants(self, **constants):
        """ adds a number of constants to the current context """
        return self._append(Constants(constants))

    
    def __init__(self):
        self._stageHead    = None
        self._stageTail    = None

    def __getattr__(self, attr):
        return getattr(self._stageHead.stage, attr)
          
    def _append(self, stage):
        """ adds an additional stage to the singly-lined list """
        link = _LinkItem(stage)
        if not self._stageHead:
            self._stageHead = link
            self._stageTail = link
        else:
            self._stageTail.next = link
            self._stageTail = link
        return self

    def build(self, data = None, context = None):
        """ builds a flow stack for execution

            This method creates a new flow stack and binds it to the
            first stage of the flow and the seed data / context.
            The stack object returned should be either "run()"
            if not in the context of Twisted, or should have iterate()
            called on it subsequent times.
        """
        assert self._stageHead, "What? A flow without stages?"
        return _Stack(self._stageHead, data, context)

    def execute(self, data = None, context = None):
        """ builds and runs a flow stack w/o pause function

            This method is primarly for testing without requiring
            a Twisted reactor.   See TwistedFlow below for a better
            version of "run" that is more twisted friendly.
        """
        stack = self.build(data, context)
        while stack.iterate(): pass

class Stage:
    def __call__(self, flow, data):
        pass
 
class Constants(Stage):
    def __init__(self, constants):
        self.constants = constants
    def __call__(self, flow, data):
        for (key, val) in self.constants.items():
            setattr(flow.context, key, val)
        flow.push(ret)

class Callable(Stage):
    def __init__(self, callable, skip = None):
        self.callable    = callable
        self.skip        = skip
    def __call__(self, flow, data):
        ret = self.callable(data)
        if ret is PauseFlowValue: return 1
        if ret is not self.skip:
            flow.push(ret)

class Sequence(Stage):
    def __init__(self, callable, onFinish = None):
        self.callable    = callable
        self.onFinish    = onFinish
        self.withContext = (2 == getArgumentCount(callable, 1))
      
    def __call__(self, flow, data):
        if self.withContext:
            ret = self.callable(flow.context,data)
        else:
            ret = self.callable(data)
        if ret is PauseFlowValue: return 1
        if ret is not None:
            next = iter(ret).next
            flow.push(next, self.iterate)
    
    def iterate(self, flow, next):
        try:
            data = next()
            if data is PauseFlowValue: return 1
            flow.push(next, self.iterate)
            flow.push(data)
        except StopIteration:
            if self.onFinish:
                if self.withContext:
                    ret = self.onFinish(flow.context)
                else:
                    ret = self.onFinish()

class _Merge(Stage):
    """
       A base class for both Reduce and Merge, performing
       the common functionality of setting up an aggregation
       bucket in the current context, etc.
    """
    def __init__(self, callable, start = None, skip = None):
        self.bucket   = "_%d" % id(self)
        self.start    = start
        self.callable = callable
        self.skip     = skip
        self.withContext = (3 == getArgumentCount(callable, 2))
 
    def __call__(self, flow, data):
        cntx = flow.context
        if not hasattr(cntx, self.bucket): 
            start = self.start
            if callable(start):
                startArgs = getArgumentCount(start, 0)
                if startArgs > 0: start = start(flow.context)
                else: start = start()
            flow.addFlush(flow.nextLinkItem(), self.bucket, self.skip)
            setattr(cntx, self.bucket, start)
        curr = getattr(cntx, self.bucket)
        if self.withContext: curr = self.callable(cntx, curr, data)
        else:                curr = self.callable(curr, data)
        return curr

class Reduce(_Merge):
    def __init__(self, callable = lambda lst, val: lst.append(val) or lst,
                       start = lambda: [], inplace = 0, skip = None):
        _Merge.__init__(self, callable, start, skip)
        self.inplace = inplace

    def __call__(self, flow, data):
        curr = _Merge.__call__(self, flow, data)
        if curr is PauseFlowValue: return 1
        if not self.inplace:
            setattr(flow.context, self.bucket, curr)

class Merge(_Merge):
    def __init__(self, callable, start = None, skip = None):
        _Merge.__init__(self, callable, start, skip)
     
    def __call__(self, flow, data):
        curr = _Merge.__call__(self, flow, data)
        if not curr: return
        if curr is PauseFlowValue: return 1
        (aggregate_value, return_value) = curr
        setattr(flow.context, self.bucket, aggregate_value)
        if return_value is not self.skip:
            flow.push(return_value)

class Context(Stage):
    def __init__(self, onFlush = None):
        self.onFlush = onFlush

    def __call__(self, flow, data, mayskip = 0):
        flow.pushContext()
        if self.onFlush: flow.addFlush(_LinkItem(self.onFlush))
        flow.push(data)

class Filter(Stage):
    def __init__(self, callable, skip = None, rootContext = 0):
        self.callable      = callable
        self.skip          = skip
        self.rootContext = rootContext

    def __call__(self, flow, data):
        cntx = flow.context
        if self.rootContext: cntx = flow.globalContext
        ret = self.callable(cntx, data)
        if ret is PauseFlowValue: return 1
        if ret is not self.skip:
            flow.push(ret)

class Chain(Stage):
    def __init__(self, flows):
        flows = list(flows)
        flows.reverse()
        self.flows = flows
        self.bucket = str(id(self))
    def __call__(self, flow, data):
        setattr(flow.context, self.bucket, data)
        for itm in self.flows:
            flow.push((itm._stageHead,data), self.nextStage)
        flow.push(data, mayskip = 1)
    def nextStage(self, flow, data):
        (link, data) = data
        flow.pushContext()
        flow.push(data, link.stage, link.next)

class _Stack:
    """ a stack of stages and a means for their application

        The general process here is to pop the current stage,
        and call it; during the call, the stage can then add
        further items back on to the call stack.  Once the stage
        returns, the stack is checked and iteration continues.
    """
    def __init__(self, flowitem, data, context = None):
        """ bootstraps the processing of the flow

             flowitem      the very first stage in the process
             data          starting argument
             waitInterval  a useful item to slow the flow
        """
        self._stack        = []
        self.context       = _Context(context)
        self.globalContext = self.context
        self._stack.append((self.context, self._onFlushContext, None))
        self._stack.append((data, flowitem.stage, flowitem.next))
 
    def _onFlushContext(self, flow, cntx):
        """
           cleans up the context and fires onFlush events
        """
        assert flow is self
        assert flow.context is cntx
        if not(cntx._flush):
            flow.context = cntx._parent
            return 
        (link, bucket, skip) = cntx._flush.pop(0)
        data = getattr(cntx, bucket, skip)
        flow.push(cntx, self._onFlushContext)
        if data is not skip:
            assert(callable(link.stage))
            flow.push(data, link.stage, link.next)

    def pushContext(self):
        cntx = _Context(self.context)
        self.context = cntx
        self.push(cntx, self._onFlushContext)

    def addFlush(self, flowLink, bucket = None, skip = None):
        """ 
           registers a flowLink to be executed using data from the
           given bucket once the context has been popped.
        """
        self.context._flush.append((flowLink, bucket, skip))
     
    def currLinkItem(self): 
        """ returns the current stage in the process """
        return _LinkItem(self._current[1], self._current[2]) 
 
    def nextLinkItem(self):
        """ returns the next stage in the process """
        return self._current[2]
      
    def push(self, data, stage=None, next=None, mayskip = 0):
        """ pushes a function to be executed onto the stack
           
             data    argument to be passed
             stage   callable to be executed
             next    a _LinkItem for subsequent stages
        """
        if not stage:
            curr = self.nextLinkItem()
            if curr:
                stage = curr.stage
                next  = curr.next
        elif not next:
            next = self._current[2]
        if mayskip and not next: return
        assert callable(stage)
        self._stack.append((data, stage, next))
   
    
    def iterate(self):
        """ executes the current flow"""
        stack = self._stack
        while stack:
            self._current = stack.pop()
            (data, stage, next) = self._current
            if not(stage): raise "unconsumed data"
            try:
                pause = stage(self, data)
            except PauseFlow: pause = 1
            if pause:
                self.push(data, stage, next)
                return 1

class _Context:
    def __init__(self, parent = None):
        self._parent = parent
        self._flush  = []

    def __getattr__(self, attr):
        return getattr(self._parent, attr)

class _LinkItem:
    """
       a Flow is implemented as a series of Stage objects
       in a linked-list; this is the link node
        
         stage   a Stage in the linked list
         next    next _LinkItem in the list
 
    """
    def __init__(self, stage, next = None ):
        self.stage = stage
        self.next  = next


#
# END of Flow.py PROPER
#
# Following are a bunch of "homeless" items which are here
# till they find their own home.
#

class TwistedFlow(Flow):
    """ lets Flows run nicely within Twisted """
    def __init__(self, waitInterval = .05):
        Flow.__init__(self)
        self._waitInterval = waitInterval
    def execute(self, data = None, context = None):
        """ runs a flow stack with twisted.internet.reactor """
        stack = self.build(data,context)
        _MultiRun(stack.iterate, self._waitInterval)

class _MultiRun:
    """ a helper class which keeps running a callable till it is done """
    def __init__(self, callable, waitInterval = 0):
        self.callable = callable
        self.waitInterval = waitInterval
        self.iterate(starting = 1)
    def iterate(self, starting = 0):
        if starting or self.callable():
            from twisted.internet import reactor
            reactor.callLater(self.waitInterval, self.iterate)

#
# The following is a thread package which really is othogonal to
# Flow.  Flow does not depend on it, and it does not depend on Flow.
# Although, if you are trying to bring the output of a thread into
# a Flow, it is exactly what you want.   The QueryIterator is 
# just an obvious application of the ThreadedIterator.
#

class ThreadedIterator:
    """
       This is an iterator base class which can be used to build
       iterators which are constructed and run within a Flow
    """
     
    def __init__(self, data = None):
        self.data = data  
        tunnel = _TunnelIterator(self)
        self._tunnel = tunnel
     
    def __iter__(self): 
        from twisted.internet.reactor import callInThread
        callInThread(self._tunnel.process)
        return self._tunnel
     
    def next(self):
        """ 
            The method used to fetch the next value, make sure
            to return a list of rows, not just a row
        """
        raise StopIteration

class _TunnelIterator:
    """
       This is an iterator which tunnels output from an iterator
       executed in a thread to the main thread.   Note, unlike
       regular iterators, this one throws a PauseFlow exception
       which must be handled by calling reactor.callLater so that
       the producer threads can have a chance to send events to 
       the main thread.
    """
    def __init__(self, source):
        """
            This is the setup, the source argument is the iterator
            being wrapped, which exists in another thread.
        """
        self.source     = source
        self.isFinished = 0
        self.failure    = None
        self.buff       = []
     
    def process(self):
        """
            This is called in the 'source' thread, and 
            just basically sucks the iterator, appending
            items back to the main thread.
        """
        from twisted.internet.reactor import callFromThread
        try:
            while 1:
                val = self.source.next()
                self.buff.extend(val)    # lists are thread safe
        except StopIteration:
            callFromThread(self.stop)
        self.source = None
     
    def setFailure(self, failure):
        self.failure = failure
     
    def stop(self):
        self.isFinished = 1
     
    def next(self):
        if self.buff:
           return self.buff.pop(0)
        if self.isFinished:  
            raise StopIteration
        if self.failure:
            raise self.failure
        raise PauseFlow

class QueryIterator(ThreadedIterator):
    def __init__(self, pool, sql, fetchall=0):
        ThreadedIterator.__init__(self)
        self.curs = None
        self.sql  = sql
        self.pool = pool
        self.data = None
        self.fetchall = fetchall
     
    def __call__(self,data):
        self.data = data
        return self
     
    def next(self):
        if not self.curs:
            conn = self.pool.connect()
            self.curs = conn.cursor()
            if self.data: self.curs.execute(self.sql % self.data) 
            else: self.curs.execute(self.sql)
        if self.fetchall:
            res = self.curs.fetchall()
        else:
            res = self.curs.fetchmany()
        if not(res): 
            raise StopIteration
        return res
