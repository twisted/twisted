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
""" Flow ... asynchronous data flows

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
                yield lst; yield nam
                if lst.stop or nam.stop:
                    return
                yield flow.Cooperate()
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
from twisted.python.failure import Failure
from twisted.python.compat import StopIteration, iter

def wrap(obj, trap = None):
    """ Wraps various objects for use within a flow """
    if isinstance(obj, Stage):
        return obj
    if trap:
        import types
        if type(trap) == types.ClassType: 
            trap = (trap,)
    return _Iterable(obj, trap)

class Instruction:
    """ Has special meaning when yielded in a flow """

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

           iterable = DerivedStage(trap=(SpamError, EggsError))
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
    def __init__(self, trap = None):
        self._ready = 0
        if not trap: trap = tuple()
        self._trap = trap
        self.stop   = 0
        self.result = None
    def __iter__(self):
        return self
    def isFailure(self):
        """ return a boolean value if the result is a Failure """ 
        return isinstance(self.result, Failure)
    def next(self):
        """ return the current result, raising failures if specified """
        if self.stop: raise StopIteration()
        assert self._ready, "must yield flow stage before calling next()"
        self._ready = 0
        if self.isFailure(): 
            return self.result.trap(*self._trap)
        return self.result
    def _yield(self):
        """ executed during a yield statement

            This method is private within the scope of the flow
            module, it is used by one stage in the flow to ask
            for the next stage to produce.   If a value is 
            returned, then it shall be passed all the way up
            the call chain (useful for Cooperate) without 
            changing the execution path.
        """
        self._ready = 1
        self.result = None


class _Iterable(Stage):
    """ Wraps iterables (generator/iterator) for use in a flow """      
    def __init__(self, iterable, trap):
        Stage.__init__(self, trap)
        try:
            self._next = iter(iterable).next
        except TypeError:
            iterable = iterable()
            self._next = iter(iterable).next
        self._next_stage  = None
        self._stop_next = 0
    def _yield(self):
        """ executed during a yield statement

            To fetch the next value, the Iterable first checks to 
            see if there is a next stage which must be processed first.  
            If so, it does that.   Note that the next stage does not need
            to be remembered, as the current stage will yield the same 
            object again if requires further processing.   Also, this
            enables more than one next stage to be used.

            After this, it calles the wrapped generator's next method,
            and process the result.   If the result is a Stage, then
            this is queued for execution.  Otherwise, either Cooperate
            object is returned, or None is returned indicating that
            a result was produced.
        """
        Stage._yield(self)
        if self._stop_next or self.stop:
            self.stop = 1
            return
        while 1:
            next = self._next_stage
            if next:
                result = next._yield()
                if result: return result
                self._next_stage = None 
            try:
                result = self._next()
                if isinstance(result, Instruction):
                    if isinstance(result, Stage):
                        self._next_stage = result
                        continue
                    return result
                self.result = result
            except Cooperate, coop: 
                return coop
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

        Basically, this Stage can be used for merging two iterators 
        into a single iterator, all while maintaining the ability to 
        pause the iterator using Cooperate.   Note, that the order of
        the items returned is not necessarly predictable.
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

        This converts a Stage into the Iterator interface for 
        use in situation where blocking for the next value is
        acceptable.   Basically, it wraps any iterator/generator
        as a Stage object, and then eats any Cooperate results.

        This is largely helpful for testing or within a threaded
        environment.  It converts other stages into one which 
        does not emit cooperate events.
    """
    def __init__(self, stage):
        self._stage = wrap(stage)
    def __iter__(self):
        return self
    def next(self):
        """ fetch the next value from the Stage flow """
        stage = self._stage
        while 1:
            result = stage._yield()
            if result:
                if isinstance(result, Cooperate):
                    from time import sleep
                    sleep(result.timeout)
                    continue
                raise TypeError("Invalid stage result")
            return stage.next()

from twisted.internet import defer
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
        @param delay:           delay when scheduling reactor.callLater
        @param failureAsResult  if true, then failures will be added to 
                                the result list provided to the callback,
                                otherwise the first failure results in 
                                the errback being called with the failure.
        """
        defer.Deferred.__init__(self)
        self.failureAsResult = failureAsResult
        self._results = []
        self._stage = wrap(stage)
        from twisted.internet import reactor
        reactor.callLater(0, self._execute)
    def _execute(self):
        cmd = self._stage
        while 1:
            result = cmd._yield()
            if cmd.stop:
                if not self.called:
                    self.callback(self._results)
                return
            if result:
                if isinstance(result, Cooperate):
                    from twisted.internet import reactor
                    reactor.callLater(result.timeout, self._execute)
                    return
                raise TypeError("Invalid stage result")
            if not self.failureAsResult: 
                if cmd.isFailure():
                    self.errback(cmd.result)
                    return
            self._results.append(cmd.result)
        
#
# The following is a thread package which really is othogonal to
# flow.  Flow does not depend on it, but it does depend on flow.Cooperate
# Although, if you are trying to bring the output of a thread into
# a flow, it is exactly what you want.   The QueryIterator is 
# just an obvious application of the ThreadedIterator.
#

class ThreadedIterator:
    """
       This is an iterator which tunnels output from an iterator
       executed in a thread to the main thread.   Note, unlike
       regular iterators, this one throws a Cooperate exception
       which must be handled by calling reactor.callLater so that
       the producer threads can have a chance to send events to 
       the main thread.

       Basically, the 'init' and 'next' method of subclasses are
       executed in this alternative thread.  The results of 'next'
       are marshalled back into the primary thread.  If when the
       main thread data is not available, then a particular 
       exception.
    """
    def __init__(self, extend = 0):
        class _Tunnel:
            def __init__(self, source, extend ):
                """
                    This is the setup, the source argument is the iterator
                    being wrapped, which exists in another thread.
                """
                self.source     = source
                self.stop       = 0
                self.failure    = None
                self.buff       = []
                self.extend     = extend
            def process(self):
                """
                    This is called in the 'source' thread, and 
                    just basically sucks the iterator, appending
                    items back to the main thread.
                """
                try:
                    self.source.init()
                except: 
                    self.failure = Failure()
                try:
                    while 1:
                        val = self.source.next()
                        if self.extend:
                            self.buff.extend(val)
                        else:
                            self.buff.append(val)
                except StopIteration:
                    self.stop = 1
                except: 
                    if not self.failure:
                        self.failure = Failure()
                self.source = None
            def next(self):
                if self.buff:
                   return self.buff.pop(0)
                if self.stop:  
                    raise StopIteration
                if self.failure:
                    raise self.failure
                raise Cooperate()
        tunnel = _Tunnel(self, extend)
        self._tunnel = tunnel

    def __iter__(self): 
        from twisted.internet.reactor import callInThread
        callInThread(self._tunnel.process)
        return self._tunnel
    
    def init(self):
        pass   
     
    def next(self):
        raise StopIteration

class QueryIterator(ThreadedIterator):
    def __init__(self, pool, sql, fetchall=0):
        ThreadedIterator.__init__(self, extend = 1 )
        self.curs = None
        self.sql  = sql
        self.pool = pool
        self.fetchall = fetchall
     
    def init(self):
        conn = self.pool.connect()
        self.curs = conn.cursor()
        self.curs.execute(self.sql)
 
    def next(self):
        res = None
        if self.curs:
            if self.fetchall:
                res = self.curs.fetchall()
                self.curs = None
            else:
                res = self.curs.fetchmany()
        if not(res): 
            self.curs = None
            raise StopIteration
        return res
