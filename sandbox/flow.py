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

class YieldIteration(Exception):
   '''
      This exception can be used as a signal from an
      iterator returned from an IFlowFunction; the Flow
      object could then reschedule itself in the event
      queue so that other operations can proceed.   In
      this case, the iterator's next() will just be 
      called at a later time.
   '''


initialState = "__initial__"
failureState = "__failure__"

class IFlowFunction:
    ''' 
       This is an interface for a function (with attributes) 
       which participates in a given Flow.  It is typical to 
       implement this using a function given attributes.  Every
       attribute may be missing to provide minimal behavior.

       isIterable   This is true if the function returns an 
                    iterable object; in 2.1 this is either a
                    list or array or something with a next()
                    function.  In short, this means that for
                    each application of the function, 0..M
                    subordinate calls will be made.  

       nextState    If the next state of the function is fixed,
                    then this attribute can be set.  In this 
                    case, the return value from the function 
                    call can just be the value, rather than 
                    a (state, value) tuple.

                    If nextState is not provided and if isIterable
                    is true, then each call to next() in the 
                    iteration must be a (state,value) tuple.

       stopValue    This is a value which will stop recursion,
                    it defaults to None when not provided.

       Note: if none of these attributes are provided, then the
       function is expected to return a tuple with two items,
       a (state, value) or None to stop the flow.
    '''
    def __call__(self, data):
        '''
            When the function is invoked, it is passed a single 
            argument, the data for the call.  To stop further
            interaction within the Flow, this function should just
            return None.  Otherwise, the return value depends upon
            the various attributes of the function.
        '''
        pass
    def onFinish(self):
        '''
            This function attribute, if present, will be called after
            all subordinate flows have finished.  It can be used for
            an 'end-list' indicator, etc.
        '''
        pass
    def onFailure(self, state, data, failure):
        '''
            This function attribute, if present, will be called when
            ever an error occurs in processing any of the children, 
            This callable is applied with the state, and data of 
            the failing call.  Either None, or a (state, value) 
            tuple should be returned from this function; if a tuple 
            is returned, then processing continues from where it left 
            off; perhaps visiting more children in the iteration (if any).
        '''
        pass

class Flow:
    '''
       This is a state machine driven data consumer.

       Flow objects are used to run data from a producer, 
       such as a database query, through various filter functions 
       until the data is eventually consumed and None is returned.

       As data is introduced into the Flow using the 'run' 
       method, the Flow looks up the appropriate handler, and 
       calls it with the data provided.  If the callee wishes
       processing to continue, it responds with a (state,data)
       tuple, which is then used iteratively.  To stop the 
       flow, the callee simply returns None (the default).

       To have any effect, the Flow must have one or more 
       handlers which have been registered for each state.
       Only one handler is active for a given state at any
       time, thus this object uses the mapping key/value
       synax for handlers.
   '''
    def __init__(self, *bases):
        '''
           Initializes a Flow object, optionally using
           one or more subordinate flow objects for 
           default behavior.  The stack is used when the
           currently executing object wants to be notified
           that all children have finished processing. 
        '''
        self.states       = {}
        self.bases        = bases or []
        self.stack        = []
        self.waitInterval = 0
    #     
    def register(self, func, state = initialState,
                 nextState = None, isIterable = 0, 
                 onFinish = None, onFailure = None,
                 stopValue = None):
        '''
            This allows the registration of callback functions
            which are applied whenever an appropriate event of
            a given state is encountered.  Each callback item,
            run, start, and finish can either be a function
            or it can be a tuple with function first, and the
            default final state second.   If a final state is
            provided, then the function can just return a value.
            Otherwise, if the final state is None or not provided,
            then the function must return a tuple.
        '''
        tpl = (func, nextState, isIterable, onFinish, onFailure, stopValue)
        self.states[state] = tpl
    #
    def __setitem__(self,key,val): 
        self.register(key,val)
    #
    def _lookup(self,state):
        '''
           Searches for the appropriate handler in the
           current flow, scouring through 'base' flows
           if they are provided.
        '''
        func = self.states.get(state,None)
        if not func:
            for base in self.bases:
                func  = base.states.get(state,None)
                if func: break
        if func: return func
        errmsg = "\nstate '%s' not found for:%s"
        raise KeyError(errmsg % (state, str(self)))
    #
    def run(self, data = None, state=initialState):
        '''
           This executes the current flow, given empty
           starting data and the default initial state.
        '''
        trace("running flow")
        stack = self.stack
        if not(stack): 
            stack.append((state, data, None, None, None))
        while stack:
            (state, data, finish, itr, stop) = stack[-1]
            if finish:
                finish()
                stack.pop()
                continue
            elif itr:
                trace("-> iterator")
                try:
                    data = itr.next()
                    if data is stop: continue
                    if not state:
                        (state, data) = data
                        if data is stop: continue
                except StopIteration:
                    trace("-> stop")
                    stack.pop()
                    continue
                except YieldIteration:
                    trace("-> yield")
                    from twisted.internet import reactor
                    reactor.callLater(self.waitInterval, self.run)
                    return
            else:
                stack.pop()
            tpl = self._lookup(state)
            (func, state, isIterable, finish, failure, stop) = tpl
            if finish: stack.append((state, None, finish, None, stop))
            data = func(data)
            trace("-> item")
            if isIterable or getattr(func,'isIterable',0):
                if data:
                    data = iter(data)
                    self.stack.append((state, None, None,data, stop))
            else:
                if data is stop: continue
                if not state:
                    (state, data) = data
                    if data is stop: continue
                stack.append((state, data, None, None, stop))
        trace("end flow")
    #
    def __str__(self,indlvl=0):
        indent = "\n" + "    " * indlvl
        indent2 = indent + "        "
        return "%sFlow: %s%s%s%s%s" % (
                  indent,repr(self),indent2, 
                  indent2.join(self.states.keys()),indent,
                  "".join(map(lambda a: a.__str__(indlvl+1), self.bases)))

class _TunnelIterator:
    '''
       This is an iterator which tunnels output from an iterator
       executed in a thread to the main thread.   Note, unlike
       regular iterators, this one throws a YieldIteration exception
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
    def __iter__(self):
        '''
            This is the place where the pump starts...
        '''
        from twisted.internet.reactor import callInThread
        callInThread(self.process)
        return self
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
        raise YieldIteration

class FlowIterator:
    '''
       This is an iterator base class which can be used to build
       iterators which are constructed and run within a Flow
    '''
    def __init__(self, data):
        '''
           This method (the initializer) is called by the flow object;
           this should initialize the iterator.
        '''
        self._tunnel    = _TunnelIterator(self)
        self.data       = data
        self.__class__.isIterable = 1
    #    
    def __iter__(self):
        return self._tunnel.__iter__() 
    #
    def next(self):
        ''' 
            The method used to fetch the next value
        '''
        raise StopIteration

from twisted.enterprise.adbapi import ConnectionPool
class _FlowQueryIterator(FlowIterator):
    def __init__(self, pool, sql, data):
        FlowIterator.__init__(self,data)
        self._tunnel.append = self._tunnel.buff.extend
        conn = pool.connect()
        self.curs = conn.cursor()
        if data: self.curs.execute(sql % data) 
        else: self.curs.execute(sql)
    def next(self):
        res = self.curs.fetchmany()
        if not(res): 
            self.curs.close()
            raise StopIteration
        return res

class FlowQueryBuilder:
    isIterable = 1
    def __init__(self, pool, sql):
        self.pool = pool
        self.sql  = sql
    def __call__(self, data):
        return _FlowQueryIterator(self.pool, self.sql, data)

from twisted.enterprise.adbapi import ConnectionPool 
def testFlowConnect():
    pool = ConnectionPool("mx.ODBC.EasySoft","SomeDSN")
    def printResult(x): print x
    def printDone(): print "done"
    f = Flow()
    sql = "SOME-QUERY"
    f.register(FlowQueryBuilder(pool,sql),nextState='print')
    f.register(printResult,'print')
    f.run()

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
    f.register(CountIterator,nextState='print',onFinish=printDone)
    f.register(printResult,'print')
    f.run(5)

def testFlow():
    '''
        A very boring unit test for the Flow object
    '''

    def addOne(data):
        return "multiplyTwo", data+1
    def multiplyTwo(data):
        if data > 10:
            return "printResult", data*2
        else:
            return "addOne", data*2
    def printResult(data):
        print data
    
    f = Flow()
    f.register(addOne)
    f.register(addOne,"addOne")
    f.register(multiplyTwo, "multiplyTwo")
    f.register(printResult,"printResult")
    
    f.run(1)
    f.run(5)
    f.run(11)
    
    def forkBegin(data):
        return [("printResult", data+1), ("printResult",data+2)]
    fFork = Flow(f)
    fFork.register(forkBegin, isIterable=1)
    
    fFork.run(1)
    fFork.run(5)
    fFork.run(11)
    
    def printHTML(data):
        print "<li>%s</li>" % data
    def startList(data):  
        print "<ul>"
        return ['1','2','3']
    def finishList(): print "</ul>"
    
    fHTML = Flow(f)
    fHTML.register(printHTML, "printResult")
    fHTML.register(startList,isIterable=1,
                   nextState="printResult", onFinish=finishList)
    fHTML.run()

    def foo(data):
        return "flarbis", data / 99
    
    bad = Flow(fFork)
    bad.register(addOne)
    bad.register(foo,"multiplyTwo")
    
    bad.run(5)

if '__main__' == __name__:
    from twisted.internet import reactor
    #testFlowConnect()
    testFlowIterator()
    reactor.run()
    testFlow()
