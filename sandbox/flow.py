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
    saving the handler's state so it can be resumed later. 
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

    def addCallable(self, callable, stop=None):
        """ wraps a function or other callable for use in a flow

            This wraps a callable with a single input parameter
            and an optional output value, one-to-one behavior.
            If the return value is stop (None if you don't have 
            a return statement) then the next stage is not processed.

                def func(data):
                    # do something and then process
                    # the next stage
                    return data
             
            Optionally, if the callback happens to accept two 
            arguments rather than one, it will be passed the 
            context first and the data value second.  The context
            exists for the life of the flow, so it can be used
            to stuff away variables as needed.

                def func(context, data):
                    # context is mutable to 
                    # store all kinds of items
                    return data
            
            Note that this implementation is tail recursive, that is, 
            in most cases each callable finishes executing before the 
            next stage is pushed onto the stack.
        """
        return self._append(Callable(callable, stop))

    def addBranch(self, callable, onFinish = None):
        """ wraps an iterator; in effect one-to-many behavior

            This wraps an iterable object so that it can be used
            within a data flow.  This protocol has three stages:

                First, the callable is applied with a single argument,
                the data value from the parent data flow.   This can
                be a function returning a list, for example.  Or, it
                could be a class implementing the iterator protocol 
                with a __init__ taking a 'data' argument.
 
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
            takes no arguments.  And, just like addCallable, if the 
            callable has two arguments, then the current context 
            is passed as the first argument.
        """            
        return self._append(Branch(callable, onFinish))
    
    def addMerge(self, callable, start = None, bucket = None, 
                 passThru = 0, isGlobal = 0, inplace = 0, reduce = 1):
        """ condences results; in effect many-to-one behavior

            This stage is the opposite of the Branch stage, it accepts
            multiple calls and aggregates them.  The registration of
            this stage has several parameters:
    
                callable   the function or operator which will merge the 
                           output; the function has two paramaters, first
                           is the current accumulated value, and second is
                           the value passed via the stream; the output 
                           depends on the following parameter
    
                start      the starting value; or, if it is a callable,
                           a function taking no arguments that will be
                           applied to create a starting value
    
                bucket     the attribute name for the aggregate value,
                           if left as None, a unique bucket name will 
                           be used
   
                isGlobal   if the attribute should be attached to the
                           root context (where it will survive for the
                           life of the flow's execution) 

                passThru   If this is true, then the next stage will be
                           passed on the data as it arrives from the
                           previous stage; also the final 'notificaton'
                           of the next stage will be skipped.  This is 
                           only useful if the bucket name is provided.

                inplace    If inplace is true, then the result of the 
                           callable will not be used to set the 
                           accumulated value
 
                reduce     By reduce, we mean that incremental data is
                           not passed on to the subordinate flows.  In
                           this case, if the update is not inplace, 
                           the return value of the function gives the 
                           new aggregate value

                           Otherwise, the callable will be passing on
                           events to subsequent stages, if inplace is
                           false, then a tuple is expected; the first 
                           item in the tuple is the new aggregate, and
                           the second item is the value for subsequent
                           processing stages.  

                           Note that passThru and not(reduce) are 
                           mutually exclusive.
    
            Since reducing to a single list is often useful, the default
            parameters of this function do exactly that.   Note that this
            stage uses the most nested Context for holding the accumulation
            bucket; thus placement of Context stages could be used to 
            capture intermediate results, etc.
        """
        return self._append(Merge(callable, start, bucket, passThru, 
                                  isGlobal, inplace, reduce))

    def addMergeToList(self, passThru = 0, isGlobal = 0, bucket=None):
        """ accumulates events into a list """
        return self._append( Merge(bucket=bucket, passThru=passThru,
                                  isGlobal=isGlobal))
    
    def addContext(self, onFlush = None):
        """ adds a nested context, provides for end notification

            In a flow, introducing a branch or a callable doesn't
            necessarly create a variable context.  This is done explicitly
            with this Stage.  This context also provides a callback
            which can be used with the context is flushed, that is when
            all child processes have finished.  
        """
        return self._append(Context(onFlush))

    def addChain(self, *flows):
        """ adds one or more flows to the current flow

            In some cases it is necessary to daisy-chain flows
            together so that the stages from the chained flows
            are executed in the current flow context
        """
        return self._append(Chain(flows))
    
    def __init__(self):
        self.stageHead    = None
        self.stageTail    = None
        self.waitInterval = 0
          
    def _append(self, stage):
        """ adds an additional stage to the singly-lined list """
        link = LinkItem(stage)
        if not self.stageHead:
            self.stageHead = link
            self.stageTail = link
        else:
            self.stageTail.next = link
            self.stageTail = link
        return self

    def execute(self, data = None):
        """ executes the current flow

            This method creates a new Stack and then begins the execution 
            of the flow within that stack.  Note that this means that the 
            Flow object itself shouldn't be used for execution specific 
            information, this is what the Stack is for.
        """
        if self.stageHead:
            stack = Stack(self.stageHead, data, self.waitInterval)
            stack.execute()

class Stage:
    def __call__(self, flow, data):
        pass
 
class Callable(Stage):
    def __init__(self, callable, stop = None):
        self.callable    = callable
        self.stop        = stop
        self.withContext = (2 == getArgumentCount(callable, 1))
     
    def __call__(self, flow, data):
        """
        """
        if self.withContext:
            ret = self.callable(flow.context,data)
        else:
            ret = self.callable(data)
        if ret is not self.stop:
            flow.push(ret)

class Branch(Stage):
    def __init__(self, callable, onFinish = None):
        self.callable    = callable
        self.onFinish    = onFinish
        self.withContext = (2 == getArgumentCount(callable, 1))
      
    def __call__(self, flow, data):
        if self.withContext:
            ret = self.callable(flow.context,data)
        else:
            ret = self.callable(data)
        if ret is not None:
            next = iter(ret).next
            flow.push(next, self.iterate)
    
    def iterate(self, flow, next):
        try:
            data = next()
            flow.push(next, self.iterate)
            flow.push(data)
        except StopIteration:
            if self.onFinish:
                if self.withContext:
                    ret = self.onFinish(flow.context)
                else:
                    ret = self.onFinish()

class Merge(Stage):
    def __init__(self, callable = lambda lst, val: lst.append(val) or lst,
                       start = lambda: [], bucket = None, passThru = 0, 
                       isGlobal = 0, inplace = 0, reduce = 1):
        if not bucket: bucket = "_%d" % id(self)
        self.bucket      = bucket
        self.start       = start
        self.callable    = callable
        self.reduce      = reduce
        self.inplace     = inplace
        self.isGlobal    = isGlobal
        self.passThru    = passThru
        self.withContext = (3 == getArgumentCount(callable, 2))
        if self.passThru: assert reduce
    #
    def __call__(self, flow, data):
        if self.isGlobal: cntx = flow.global_context
        else:             cntx = flow.context
        if not hasattr(cntx, self.bucket):
             start = self.start
             if callable(start): start = start()
             setattr(cntx, self.bucket, start)
             if not self.passThru:
                 cntx.addFlush(flow.nextLinkItem(), self.bucket)
        curr = getattr(cntx, self.bucket)
        if self.withContext:
            curr = self.callable(cntx, curr, data)
        else:
            curr = self.callable(curr, data)
        if self.reduce:
            if not self.inplace:
                setattr(cntx, self.bucket, curr)
            if self.passThru:
                flow.push(data)
        else:
            if curr:
                if not self.inplace:
                    (save, curr) = curr
                    setattr(cntx, self.bucket, save)
                if curr is not None: 
                    flow.push(curr)

class Context(Stage):
    def __init__(self, onFlush = None):
        self.onFlush = onFlush

    def __call__(self, flow, data):
        cntx = _Context(flow.context)
        if self.onFlush: 
            cntx.addFlush(LinkItem(self.onFlush))
        flow.context = cntx
        flow.push(cntx, cntx.onFlush)
        flow.push(data)

class Chain(Stage):
    def __init__(self, flows):
        flows = list(flows)
        flows.reverse()
        self.flows = flows
      
    def __call__(self, flow, data):
        def start(flow, subflow):
            curr = subflow.stageHead
            flow.push(data, curr.stage, curr.next)
        for item in self.flows:
            flow.push(item, start)
        flow.push(data, mayskip = 1)

class Stack:
    """ a stack of stages and a means for their application

        The general process here is to pop the current stage,
        and call it; during the call, the stage can then add
        further items back on to the call stack.  Once the stage
        returns, the stack is checked and iteration continues.
    """
    def __init__(self, flowitem, data = None, waitInterval = 0):
        """ bootstraps the processing of the flow

             flowitem      the very first stage in the process
             data          starting argument
             waitInterval  a useful item to slow the flow
        """
        self._waitInterval = waitInterval
        self._stack   = []
        self.global_context = _Context()
        self.context = self.global_context
        self._stack.append((self.context, self.context.onFlush, None))
        self._stack.append((data, flowitem.stage, flowitem.next))
     
    def nextLinkItem(self):
        """ returns the next stage in the process """
        return self._current[2]
      
    def push(self, data, stage=None, next=None, mayskip = 0):
        """ pushes a function to be executed onto the stack
           
             data    argument to be passed
             stage   callable to be executed
             next    a LinkItem for subsequent stages
        """
        if not stage:
            curr = self.nextLinkItem()
            if curr:
                stage = curr.stage
                next  = curr.next
        elif not next:
            next = self._current[2]
        if mayskip and not next: return
        self._stack.append((data, stage, next))
     
    def execute(self):
        """ executes the current flow"""
        stack = self._stack
        while stack:
            self._current = stack.pop()
            (data, stage, next) = self._current
            if not(stage): raise "unconsumed data"
            try:
                pause = stage(self, data)
            except PauseFlow: 
                self.push(data, stage, next)
                pause = 1
            if pause:
                from twisted.internet import reactor
                reactor.callLater(self._waitInterval,self.execute)
                return 1

class _Context:
    def __init__(self, parent = None):
        self._parent = parent
        self._flush  = []
        self._dict   = {}
     
    def addFlush(self, flowLink, bucket = None):
        """ 
           registers a flowLink to be executed using data from the
           given bucket once the context has been popped.
        """
        self._flush.append((flowLink, bucket))
     
    def onFlush(self, flow, cntx):
        """
           cleans up the context and fires onFlush events
        """
        assert flow.context is self
        assert flow.context is cntx
        if not(self._flush):
            flow.context = self._parent
            return 
        (link, bucket) = self._flush.pop(0)
        data = getattr(self, bucket, None)
        flow.push(cntx, self.onFlush)
        flow.push(data, link.stage, link.next)
    
    def __getattr__(self, attr):
        return getattr(self._parent, attr)

class LinkItem:
    """
       a Flow is implemented as a series of Stage objects
       in a linked-list; this is the link node
        
         stage   a Stage in the linked list
         next    next LinkItem in the list
 
    """
    def __init__(self,stage):
        self.stage = stage
        self.next  = None

class FlowIterator:
    """
       This is an iterator base class which can be used to build
       iterators which are constructed and run within a Flow
    """
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
    #
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
                callFromThread(self.buff.extend,val)
        except StopIteration:
            callFromThread(self.stop)
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
    def __init__(self, pool, sql, fetchall=0):
        FlowIterator.__init__(self)
        self.curs = None
        self.sql  = sql
        self.pool = pool
        self.data = None
        self.fetchall = fetchall
    #
    def __call__(self,data):
        self.data = data
        return self
    #
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
            #self.curs.close()
            raise StopIteration
        return res

