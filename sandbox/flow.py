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

"""I am state machine driven data consumer"""

#from __future__ import generators

# support iterators for 2.1
try:
   StopIteration = StopIteration
except:
   class StopIteration(Exception): pass

initialState = "__initial__"
failureState = "__failure__"

(_FUNC_CONSUME,_FUNC_START,_FUNC_FINISH) = range(3)
class Flow:
    '''
       This is a state machine driven data consumer.

       Flow objects are used to dispatch data from a producer, 
       such as a database query, through various filter functions 
       until the data is eventually dispatchd. 

       As data is introduced into the Flow using the 'dispatch' 
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
           default behavior.  
        '''
        self.states       = {}
        self.bases        = bases or []
        self.stack        = []
    #     
    def register(self, dispatchHandler, state = initialState,
                 startHandler = None, finishHandler = None ):
        '''
            This allows the registration of callback functions
            which are applied whenever an appropriate event of
            a given state is encountered.
        '''
        self.states[state] = (dispatchHandler, startHandler, finishHandler)
    #
    def _lookup(self,state,fnc=_FUNC_CONSUME):
        fncs = self.states.get(state,None)
        if not fncs:
            for base in self.bases:
                fncs  = base.states.get(state,None)
                if fncs: break
        if fncs: return fncs[fnc]
        errmsg = "\nstate '%s' not found for:%s"
        raise KeyError(errmsg % (state, str(self)))
    #
    def start(self,state=initialState):
        '''
           In some cases, hierarchical behavior is useful to 
           model; if the data flow is hierarchical, this is 
           used to mark the start of a branch.
        '''
        self.stack.append(state)
        fnc = self._lookup(state,_FUNC_START)
        if fnc: fnc()
    #
    def finish(self,state=None):
        val = self.stack.pop()
        if state: assert(state == val)
        fnc = self._lookup(val,_FUNC_FINISH)
        if fnc: fnc()
    #
    def dispatch(self,data,state=initialState):
        '''
           This is the primary dispatch loop which
           processes the data until the given handlers
           return Null
        '''
        while 1:
            nextConsumer = self._lookup(state)
            tpl = nextConsumer(data)
            if not(tpl): return
            state = tpl[0]
            data  = tpl[1]
            if len(tpl) > 2:  # fork
                arr = list(tpl[1:])
                self.start(state)
                while arr: self.dispatch(arr.pop(0),state)
                self.finish(state)
                return
    #
    def __str__(self,indlvl=0):
        indent = "\n" + "    " * indlvl
        indent2 = indent + "        "
        return "%sFlow: %s%s%s%s%s" % (
                  indent,repr(self),indent2, 
                  indent2.join(self.states.keys()),indent,
                  "".join(map(lambda a: a.__str__(indlvl+1), self.bases)))
    #
    def __setitem__(self,key,val): self.register(val,key)


def _putIterationInFlow(flow, f, args, kwargs):
    """Send the results of an iteration to a flow object.
       The function called should return an object
       with a next() operator.
    """
    from twisted.internet.reactor import callFromThread
    try:
        itr = apply(f, args, kwargs)
        callFromThread(flow.start)
        while 1: callFromThread(flow.dispatch, itr.next())
    except StopIteration:
        callFromThread(flow.finish)
    except:
        callFromThread(flow.dispatch, failure.Failure(), failureState)

def runIterationInThread( f, *args, **kwargs):
    """Run the results of an iterator in a thread.

       The function passed, when arguments applied, should
       return an object with a next() method raising
       StopIteration when there isn't any more content.
       Thus a 2.2 generator works perfectly, as is any
       iterator object.  Although this will work in 2.1 
       as well.

       Returns a Flow who's events are the result of
       the iterator.
    """
    from twisted.internet.reactor import callInThread
    flow = Flow()
    callInThread(_putIterationInFlow, flow, f, args, kwargs)
    return flow

from twisted.enterprise.adbapi import ConnectionPool
class FlowConnectionPool(ConnectionPool):
    def _runQueryChunked(self, args, kw):
        conn = self.connect()
        curs = conn.cursor()
        apply(curs.execute, args, kw)
        class chunkIterator:
            def __init__(self,curs):
                self.curs = curs
                self.curr = None
            def __iter__(self): 
                return self
            def next(self):
                if not self.curr:
                    self.curr = self.curs.fetchmany()
                if not self.curr:
                    self.curs.close()
                    raise StopIteration
                return self.curr.pop(0)
        return chunkIterator(curs)
    def queryChunked(self, *args, **kw):
        """ Sets up a deferred execution query that returns
            one or more result chunks.
      
            This method returns a MultiDeferred, which is notified when
            the query has finished via its FinishCallback.
        """
        return runIterationInThread(self._runQueryChunked, args, kw)

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
    
    f.dispatch(1)
    f.dispatch(5)
    f.dispatch(11)
    
    
    def printHTML(data):
        print "<li>%s</li>" % data
    def startList():  print "<ul>"
    def finishList(): print "</ul>"
    
    fHTML = Flow(f)
    fHTML.register(printHTML,"printResult", startList, finishList)
    
    fHTML.start("printResult")
    fHTML.dispatch(1)
    fHTML.dispatch(5)
    fHTML.dispatch(11)
    fHTML.finish("printResult")
    
    def forkBegin(data):
        return "printResult", data+1, data+2
    fFork = Flow(f)
    fFork.register(forkBegin)
    
    fFork.dispatch(1)
    fFork.dispatch(5)
    fFork.dispatch(11)
    
    def foo(data):
        return "flarbis", data / 99
    
    
    bad = Flow(fFork)
    bad.register(addOne)
    bad.register(foo,"multiplyTwo")
    
    bad.dispatch(5)

def testFlowThread():
    class producer:
        def __init__(self):
            self.val = 9
        def next(self):
            val = self.val
            if val < 1: raise StopIteration
            self.val -= 1
            return val
    def bldr(): return producer()
    def printResult(x): print x
    def printDone(): print "done"
    d = runIterationInThread(bldr)
    d.register(printResult, finishHandler = printDone)

#def testFlowThreadUsingGenerator():
#    def gene(start=99):
#        while(start > 90):
#            yield start
#            start -= 1
#    def printResult(x): print x
#    def printDone(): print "done"
#    d = runIterationInThread(gene)
#    d.register(printResult, finishHandler = printDone)
#import mx.ODBC.EasySoft
#mx.ODBC.EasySoft.threadsaftey = 1
#print mx.ODBC.EasySoft.threadsaftey

def testFlowConnect():
    pool = FlowConnectionPool("mx.ODBC.EasySoft","SomeDSN")
    def printResult(x): print x
    def printDone(): print "done"
    d = pool.queryChunked("SELECT some-query")
    d.register(printResult, finishHandler = printDone)

if '__main__' == __name__:
    from twisted.internet import reactor
    testFlowThread()
#    testFlowConnect()
#    testFlowThreadUsingGenerator()
    reactor.run()
    testFlow()
