# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Axista, Inc.
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

"""
   State-machine driven data consumer
"""
def trace(str): pass
from types import TupleType
#from __future__ import generators

# support iterators for 2.1
try:
   StopIteration = StopIteration
   iter = iter
except:
   class StopIteration(Exception): pass
   class _ListIterator:
       def __init__(self,lst):
           self.lst = list(lst)
       def next():
           if self.lst: return self.lst.pop(0)
           else: raise StopIteration
   def iter(lst): 
       from types import ListType, TupleType
       if type(lst) == type([]) or type(lst) == type(tuple()):
           return _ListIterator(lst) 
       else:
           return lst.__iter__()

class PauseFlow(Exception):
   '''
      This exception can be used as a signal from a stage in the 
      flow to the flow controller.  It can occur in either the
      __call__ of the stage, or in the next() method of any
      iterator returned.   The result of this signal is that
      the entire flow mechanism is paused and recheduled in the
      main loop so that other operations in the reactor can
      proceed.   In any case, the function will be called again
      (or the iterator's next method tried) once the flow as 
      resumed.
  '''

def FlowStage(callable, onFinish = None, isIterable = None,
              isDynamic = None, stopValue = None, onFailure = None):
    ''' 
       This function constructs a FlowStage tuple which is used inside
       the Flow mechanism to track state, etc.  If an argument is provided,
       then it is used; otherwise the callable is searched for the same
       attribute, else, the default is used.

       onFinish     This function attribute, if present, will be called
                    after all subordinate flows have been finished.  It 
                    can be used as an end-of-list indicator.

       isIterable   This is true if the function returns an iterable 
                    object; in 2.1 this is either a list or array or 
                    something with a next() function.  In short, this 
                    means that for each application of the function, 
                    0..M subordinate calls will be made.  

       isDynamic    If this is true, then the return value of each call
                    is a (nextFlow, nextValue) pair, where nextFlow
                    is a Flow object (see below).

       stopValue    This is a value which will stop recursion,
                    it defaults to None when not provided.

       onFailure    This is a callable attribute, that, if present
                    will be executed when ever an error occurs processing
                    any of the children.  This callable is applied with
                    the an stack of IFlowFunction, and the current data
                    value.  The onFinish function can remedy the problem
                    by returning a valid value, or can cancel recursion
                    by returning None.   onFinish problems are propigated
                    up the flow stack if left unhandled.

       The callable itself must take one argument, a 'data' value which
       is the result of previous evaluation in the Flow.  Unless isDynamic
       or isIterable, the return value of the callable should be a single
       value, or None to stop further processing.
    '''
    def noop(*args): pass
    if onFinish   is None: onFinish   = getattr(callable, 'onFinish', noop)
    if isIterable is None: isIterable = getattr(callable, 'isIterable', 0)
    if isDynamic  is None: isDynamic  = getattr(callable, 'isDynamic', 0)
    if stopValue  is None: stopValue  = getattr(callable, 'stopValue', None)
    if onFailure  is None: onFailure  = getattr(callable, 'onFailure', noop)
    return (callable, onFinish, isIterable, isDynamic, stopValue, onFailure)

class FlowStageLink:
    '''A simple singly-linked list'''
    def __init__(self,stage):
        self.stage = stage
        self.next  = None

(_STACK_FINISH, _STACK_ITERATOR, _STACK_DYNAMIC, _STACK_STAGE) = range(4)
class Flow:
    '''
       This is a state machine driven data consumer.  Flow stages are
       used to run data from a producer, such as a database query, 
       through various filter functions until the data is eventually 
       consumed and None is returned.

       As data is introduced into the Flow using the 'run' method, the 
       Flow looks up the appropriate handler, and calls it with the data 
       provided from the previous stage.  If the callee wishes processing 
       to continue, it responds with a value (which is interpreted 
       accodring to the isDynamic and isIterable flags).  To stop the
       flow, the callee simply returns None.
   '''
    def __init__(self):
        '''
           Initializes a Flow object.  Processing starts at initialStage
           and then proceeds recursively.  Note that the stages are 
           implemented as a singly-linked list, where each link is
           an array containing a FlowStage, and the next link.
        '''
        self.stageHead    = None
        self.stageTail    = None
        self.callStack    = None
        self.waitInterval = 0
    #     
    def addStage(self, callable, onFinish = None, isIterable = None,
                 isDynamic = None, stopValue = None, onFailure = None):
        '''
            This appends an additional stage to the singly-linked
            list, starting with stageHead.
        '''
        stage = FlowStage(callable, onFinish, isIterable,
                          isDynamic, stopValue, onFailure)
        link = FlowStageLink(stage)
        if not self.stageHead:
            self.stageHead = link
            self.stageTail = link
        else:
            self.stageTail.next = link
            self.stageTail = link

    def run(self, data = None, linktail = None):
        '''
           This executes the current flow, given empty
           starting data and the default initial state.
        '''
        assert not linktail, "not implemented"
        stack = self.callStack
        if not stack:
            self.callStack = stack = []
            link = self.stageHead
            stack.append((_STACK_STAGE, (link, data)))
        while stack:
            (kind, param) = stack[-1]
            if _STACK_FINISH == kind:
                param()
                stack.pop()
                continue
            if _STACK_DYNAMIC == kind:
                (flow, data, linknext) = param
                ret = flow.run(data, linknext)
                if ret: return ret  # paused
                stack.pop()
                continue         
            if _STACK_ITERATOR == kind:
                (iterator, stop, linknext) = param
                try:
                    data = iterator.next()
                    if data is stop: 
                        continue
                    param = (linknext, data)
                except StopIteration:
                    stack.pop()
                    continue
                except PauseFlow:
                    from twisted.internet import reactor
                    reactor.callLater(self.waitInterval, self.run)
                    return 1
            (link, data) = param
            (func, finish, isIterable, isDynamic, stop, failure) = link.stage
            if _STACK_STAGE == kind: stack.pop()
            if finish: stack.append((_STACK_FINISH,finish))
            data = func(data)
            if data is stop: continue
            if isDynamic:
               (data, flow) = data
               stack.append((_STACK_DYNAMIC,(flow, data, link.next )))
               continue
            if isIterable:
                 iterator = iter(data)
                 param = (iterator, stop, link.next)
                 stack.append((_STACK_ITERATOR,param))
                 continue
            stack.append((_STACK_STAGE,(link.next,data)))
    #
    def __call__(self, data):
        self.run(data)

def testFlow():
    '''
        Test basic Flow operation
    '''
  
    def dataSource(data):  
        return [1, 1+data, 1+data*2]
    def addOne(data): return  data+1
    def printResult(data): print data
    def finished(): print "done"
    
    sf = Flow()
    sf.addStage(dataSource, isIterable = 1, onFinish=finished)
    sf.addStage(addOne)
    sf.addStage(printResult)
    sf.run(3)

    def dynfnc(data):
        if data < 3:
           return (data, sf)
    cf = Flow()
    cf.addStage(dynfnc, isDynamic = 1)
    cf.run(2)
    cf.run(4)

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
        self.buff       = list()
        self.append     = self.buff.append
    #
    def __iter__(self): return self
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

class FlowIterator:
    '''
       This is an iterator base class which can be used to build
       iterators which are constructed and run within a Flow
    '''
    def __init__(self):
        '''
            This sets up the iterator before it is even added
            to the flow object.
        '''
        self.isIterable = 1
    #
    def __call__(self,data):
        from twisted.internet.reactor import callInThread
        self.data = data  
        tunnel = _TunnelIterator(self)
        callInThread(tunnel.process)
        return tunnel
    #
    def next(self):
        ''' 
            The method used to fetch the next value
        '''
        raise StopIteration

def testFlowIterator():
    class CountIterator(FlowIterator):
        def next(self): # this is run in a separate thread
            print "next"
            from time import sleep
            sleep(.5)
            val = self.data
            if not(val):
                print "done counting"
                raise StopIteration
            self.data -= 1
            return val
    def printDone(): print "done"
    def printResult(x): print x
    f = Flow()
    f.waitInterval = 1
    f.addStage(CountIterator(),onFinish=printDone)
    f.addStage(printResult)
    f.run(5)


class FlowQueryIterator(FlowIterator):
    def __init__(self, pool, sql):
        FlowIterator.__init__(self)
        self.curs = None
        self.sql  = sql
        self.pool = pool
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
        res = self.curs.fetchmany()
        if not(res): 
            self.curs.close()
            raise StopIteration
        return res

def testFlowConnect():
    from twisted.enterprise.adbapi import ConnectionPool
    pool = ConnectionPool("mx.ODBC.EasySoft","<somedsn>")
    def printResult(x): print x
    def printDone(): print "done"
    sql = "<somequery>"
    f = Flow()
    f.waitInterval = 1
    f.addStage(FlowQueryIterator(pool,sql),onFinish=printDone)
    f.addStage(printResult)
    f.run()

if '__main__' == __name__:
    from twisted.internet import reactor
    testFlow()
    testFlowIterator()
    #testFlowConnect()
    reactor.callLater(10,reactor.stop)
    reactor.run()
