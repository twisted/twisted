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
from __future__ import nested_scopes

""" 
Flow ... asynchronous data flows

    This module provides a mechanism for using async data flows through
    the use of generators.  While this module does not use generators in
    its implementation, it isn't very useable without them.   A data flow
    is constructed with a top level generator, which can have three 
    types of yield statements:  flow.Cooperate, flow.Iterable, or
    any other return value with exceptions wrapped using Failure

    An example program...

        from __future__ import generators
        import flow
        def producer():
            lst = flow.wrap([1,2,3])
            nam = flow.wrap(['one','two','three'])
            while 1:
                # these are flow.Iterable
                yield lst
                yield nam
                if lst.stop or nam.stop:
                    return
                yield flow.Cooperate()
                # this is a result
                yield (lst.result, nam.result)
        
        def consumer():
            title = flow.wrap(['Title'])
            yield title
            print title.next()
            lst = flow.wrap(producer())
            yield lst
            for val in lst:
                print val
                yield lst
        
        for x in flow.Block(consumer()):
            print x

    produces the output:

        Title
        (1, 'one')
        (2, 'two')
        (3, 'three')
        
"""

import time, types
from twisted.python.failure import Failure
from twisted.python.compat import StopIteration, iter, isinstance
from twisted.internet import defer, reactor

def wrap(obj, *trap):
    """ Wraps various objects for use within a flow """
    if isinstance(obj, Stage):
        return obj

    if isinstance(obj, defer.Deferred):
        return DeferredWrapper(obj)

    try:
        # this is going to pass for 'foo', is that good?
        return Iterable(obj, *trap)
    except TypeError: 
        # iteration over non-sequence 
        pass

    raise ValueError, "A wrapper is not available for %r" % (obj,)

class Instruction:
    """ Has special meaning when yielded in a flow """
    pass

Continue = Instruction()

class Cooperate(Instruction):
    """ Requests that processing be paused so other tasks can resume

        Yield this object when the current chain would block or periodically
        during an intensive processing task.   The flow mechanism uses these
        objects to signal that the current processing chain should be paused
        and resumed later.  This allows other delayed operations to be
        processed, etc.
    """
    def __init__(self, timeout = 0):
        self.timeout = timeout

class Stage(Instruction):
    """ Processing component in the current flow stack

        This is the primary component in the flow system, it is an
        iterable object which must be passed to a yield statement 
        before each call to next().   Usage...

           iterable = DerivedStage( ... , SpamError, EggsErrorx))
           yield iterable
           for result in iterable:
               // handle good result, or SpamError or EggsError
               yield iterable 

        Alternatively, the following member variables can be used
        instead of next()

            stop    This is true if the underlying generator has 
                    finished execution (raised a StopIteration or returned)

            result  This is the result of the generator if it is active, 
                    the result may be a fail.Failure object if an 
                    exception was thrown in the nested generator.

        For the following usage:

             iterable = DerivedStage()
             while 1:
                 yield iterable
                 if iterable.stop: break
                 if iterable.isFailure():
                     // handle iterable.result as a Failure
                 else:
                     // handle iterable.result

    """      
    def __init__(self, *trap, **kwargs):
        self._ready = 0
        self._trap = trap
        self.chunked = kwargs.get('chunked', 0)
        self.stop   = 0
        self.result = None
    
    def __iter__(self):
        return self

    def isFailure(self):
        """ return a boolean value if the result is a Failure """ 
        return isinstance(self.result, Failure)

    def next(self):
        """ return the current result, raising failures if specified """
        if self.stop:
            raise StopIteration()
        assert self._ready, "must yield flow stage before calling next()"
        self._ready = 0
        if self.isFailure(): 
            return self.result.trap(*self._trap)
        return self.result

    def _yield(self):
        """ executed during a yield statement by previous stage

            This method is private within the scope of the flow module, 
            it is used by one stage in the flow to ask a subsequent
            stage to produce its value.  The result of the yield is 
            then stored in self.result and is an instance of Failure
            if a problem occurred.
        """
        self._ready = 1
        self.result = None

class Iterable(Stage):
    """ Wrapper for iterable objects, pass in a next() function

        This wraps functions (or bound methods).    Execution starts with
        the initial function.   If the return value is a Stage, then 
        control passes on to that stage for the next round of execution.  
        If the return value is Cooperate, then the chain of Stages is
        put on hold, and this return value travels all the way up the
        call stack so that the underlying mechanism can sleep, or 
        perform other tasks, etc.  All other non-Instruction return 
        values, Failure objects included, are passed back to the 
        previous stage via self.result

        All exceptions signal the end of the Stage.  StopIteration 
        means to stop without providing a result, while all other
        exceptions provide a Failure self.result followed by stoppage.
    """
    def __init__(self, iterable, *trap):
        Stage.__init__(self, *trap)
        self._iterable   = iter(iterable)
        self._next_stage = None
        self._stop_next  = 0

    def _yield_next(self, result):
        """ Fetch the next value from the underlying callable """
        if isinstance(result, Instruction):
            if isinstance(result, Stage):
                self._next_stage = result
                return Continue
            return result
        if isinstance(result, defer.Deferred):
            self._next_stage = DeferredWrapper(result)
            return Continue
        self.result = result

    def _yield(self):
        """ executed during a yield statement """
        Stage._yield(self)
        if self._stop_next or self.stop:
            self.stop = 1
            return
        while 1:
            next = self._next_stage
            if next:
                result = next._yield()
                if result: 
                    return result
                self._next_stage = None 
            try:
                ret = self._yield_next(self._iterable.next())
                if ret is Continue: 
                    continue
                return ret
            except StopIteration:
                self.stop = 1
            except Failure, fail:
                self.result = fail
                self._stop_next = 1
            except:
                self.result = Failure()
                self._stop_next = 1
            return

class Merge(Stage):
    """ Merges two or more Stages results into a single stream

        This Stage can be used for merging two stages into a single
        stage, all while maintaining the ability to pause during Cooperate.
        Note that while this code may be deterministic, applications of
        this module should not depend upon a particular order.
    """
    def __init__(self, *stages):
        Stage.__init__(self)
        self._queue = []
        for stage in stages:
            self._queue.append(wrap(stage))
        self._cooperate = None
        self._timeout = None

    def _yield(self):
        Stage._yield(self)
        while self._queue:
            curr = self._queue.pop(0)
            result = curr._yield()
            if result: 
                if isinstance(result, Cooperate):
                    self._queue.append(curr)
                    if self._cooperate is curr:
                        return Cooperate(self._timeout)
                    if self._cooperate is None:
                        self._cooperate = curr
                        self._timeout = result.timeout
                        continue
                    if self._timeout > result.timeout:
                         self._timeout = result.timeout
                    continue
                raise TypeError("Unsupported flow instruction")
            self.result = curr.result
            if not curr.stop:
                self._queue.append(curr)
                return
        self.result = None
        self.stop = 1

class Block(Stage):
    """ A stage which Blocks on Cooperate events

        This converts a Stage into an iterable which can be used 
        directly in python for loops and other iteratable constructs.
        It does this by eating any Cooperate values and sleeping.
        This is largely helpful for testing or within a threaded
        environment.  It converts other stages into one which 
        does not emit cooperate events.
    """
    def __init__(self, stage):
        Stage.__init__(self)
        self._stage = wrap(stage)

    def next(self):
        """ fetch the next value from the Stage flow """
        stage = self._stage
        while 1:
            result = stage._yield()
            if result:
                if isinstance(result, Cooperate):
                    time.sleep(result.timeout)
                    continue
                raise TypeError("Invalid stage result")
            return stage.next()

class CooperateDeferred(Cooperate):
    """ Cooperate, with indirect rescheduling

        This is similar to cooperate, in that all objects on the
        call stack are popped; but differs in that it registers the
        flow.Deferred's execute function instead of using callLater
    """
    def __init__(self, deferred):
        self.deferred = deferred

class DeferredWrapper(Stage):
    """ Wraps a Deferred object into a stage

        Ideally, this could be done better with more indepth
        knowledge of the reactor, i.e. instead of returning
        Cooperate, it could return a WaitFor object, which
        would then cause the stream to only be resumed once
        the deferred has finished
    """
    def __init__(self, deferred, *trap):
        Stage.__init__(self, *trap)
        deferred.addBoth(self._callback)
        self._cooperate = CooperateDeferred(deferred)
        self._result    = None
        self._stop_next = 0

    def _callback(self, res):
        self._result = res

    def _yield(self):
        Stage._yield(self)
        if self.stop or self._stop_next:
            self.stop = 1
            return
        if not self._result:
            return self._cooperate
        if self._result:
            self.result = self._result
            self._stop_next = 1
#
# Items following this comment depend upon twisted.internet
#

class Threaded(Stage):
    """ A stage which runs a blocking iterable in a separate thread

        This stage tunnels output from an iterable executed in a separate
        thread to the main thread.   This process is carried out by 
        a result buffer, and returning Cooperate if the buffer is
        empty.   The wrapped iterable's __iter__ and next() methods
        will only be invoked in the spawned thread.

        This can be used in one of two ways, first, it can be 
        extended via inheritance; with the functionality of the
        inherited code implementing next(), and using init() for
        initialization code to be run in the thread.

        If the iterable happens to have a chunked attribute, and
        that attribute is true, then this wrapper will assume that
        data arrives in chunks via a sequence instead of by values.
    """
    def __init__(self, iterable, *trap):
        Stage.__init__(self, trap)
        self._iterable  = iterable
        self._stop      = 0
        self._buffer    = []
        self._cooperate = Cooperate()
        if getattr(iterable, 'chunked', 0):
            self._append = self._buffer.extend
        else:
            self._append = self._buffer.append
        reactor.callInThread(self._process)

    def _process(self):
        """ pull values from the iterable and add them to the buffer """
        try:
            self._iterable = iter(self._iterable)
        except: 
            self._buffer.append(Failure())
        else:
            try:
                while 1:
                    self._append(self._iterable.next())
            except StopIteration:
                pass
            except: 
                self._buffer.append(Failure())
        self._stop = 1

    def _yield(self):
        """ update locals from the buffer, or return Cooperate """
        Stage._yield(self)
        if self._buffer:
            self.result = self._buffer.pop(0)
            return
        if self._stop:
            self.stop = 1
            return
        return self._cooperate

class Deferred(defer.Deferred):
    """ wraps up a Stage with a Deferred interface
 
        In this version, the results of the Stage are used to 
        construct a list of results and then sent to deferred.  Further,
        in this version Cooperate is implemented via reactor's callLater.

            from twisted.internet import reactor
            import flow
            
            def res(x): print x
            d = flow.Deferred([1,2,3])
            d.addCallback(res)
            reactor.iterate()

    """

    def __init__(self, stage, failureAsResult = 0):
        """initialize a DeferredFlow
        @param stage:           a flow stage, iterator or generator
        @param failureAsResult  if true, then failures will be added to 
                                the result list provided to the callback,
                                otherwise the first failure results in 
                                the errback being called with the failure.
        """
        defer.Deferred.__init__(self)
        self.failureAsResult = failureAsResult
        self._results = []
        self._stage = wrap(stage)
        reactor.callLater(0, self._execute)

    def _execute(self, dummy = None):
        cmd = self._stage
        while 1:
            result = cmd._yield()
            if cmd.stop:
                if not self.called:
                    self.callback(self._results)
                return
            if result:
                if isinstance(result, Cooperate):
                    if isinstance(result, CooperateDeferred):
                        result.deferred.addBoth(self._execute)
                    else:
                        reactor.callLater(result.timeout, self._execute)
                    return
                raise TypeError("Invalid stage result")
            if not self.failureAsResult: 
                if cmd.isFailure():
                    self.errback(cmd.result)
                    return
            self._results.append(cmd.result)

#
# This only depends upon twisted.enterprise.adbapi or any
# other 'pool' object which has a connect() method returning
# a DBAPI 2.0 database connection
#

class QueryIterator:
    """ Converts a database query into a result iterator """

    def __init__(self, pool, sql, fetchmany=0, fetchall=0):
        self.curs = None
        self.sql = sql
        self.pool = pool
        if fetchmany: 
            self.next = self.next_fetchmany
            self.chunked = 1
        if fetchall:
            self.next = self.next_fetchall
            self.chunked = 1  

    def __iter__(self):
        conn = self.pool.connect()
        self.curs = conn.cursor()
        self.curs.execute(self.sql)
        return self

    def next_fetchall(self):
        if self.curs:
            ret = self.curs.fetchall()
            self.curs = None
            return ret
        raise StopIteration
    
    def next_fetchmany(self):
        ret = self.curs.fetchmany()
        if not ret:
            raise StopIteration
        return ret

    def next(self):
        ret = self.curs.fetchone()
        if not ret: 
            raise StopIteration
        return ret
