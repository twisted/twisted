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
""" Flow ... async data flow

    This module provides a mechanism for using async data flows through
    the use of generators.  While this module does not use generators in
    its implementation, it isn't very useable without them.   A data flow
    is constructed with a top level generator, which can have three 
    types of yield statements:  flow.Cooperate, flow.Generator, or
    any other return value with exceptions wrapped using failure.Failure
    An example program...

        from __future__ import generators
        import flow
        def producer():
            lst = flow.Generator([1,2,3])
            nam = flow.Generator(['one','two','three'])
            while 1:
                yield lst; yield nam
                if lst.stop or nam.stop: 
                    return
                yield (lst.result, nam.result)
    
        def consumer():
            title = flow.Generator(['Title'])
            yield title
            print title.getResult()
            lst = flow.Generator(producer())
            try:
                while 1:
                    yield lst
                    print lst.getResult()
            except flow.StopIteration: pass
    
        flow.Flow(consumer()).execute()

    produces the output:

        Title
        (1, 'one')
        (2, 'two')
        (3, 'three')
        
"""
from twisted.python import failure
from twisted.python.compat import StopIteration, iter

class FlowCommand: 
    """ Objects given special meaning when returned from yield """
    pass

class Cooperate(FlowCommand):
    """ Represents a request to delay and let other events process

        Objects of this type are returned within a flow when
        the flow would block, or needs to sleep.  This object
        is then used as a signal to the flow mechanism to pause
        and perhaps let other delayed operations to proceed.
    """
    def __init__(self, timeout = 0):
        self.timeout = timeout

class Generator(FlowCommand):
    """ Wraps a generator or other iterator for use in a flow 

        Creates a nested generation stage (a producer) which can provide
        zero or more values to the current stage (the consumer).  After 
        a yield of this object when control has returned to the caller,
        this object will have two attributes:

            stop    This is true if the underlying generator has not 
                    been started (a yield is needed) or if the underlying
                    generator has raised StopIteration

            result  This is the result of the generator if it is active, 
                    the result may be a fail.Failure object if an 
                    exception was thrown in the nested generator.
    """      
    def __init__(self, iterable):
        self._next  = iter(iterable).next
        self.result = None
        self.stop   = 1
    def isFailure(self):
        """ return a boolean value if the result is a Failure """ 
        if self.stop: raise StopIteration()
        return isinstance(self.result, failure.Failure)
    def getResult(self):
        """ return the result, or re-throw an exception on Failure """
        if self.isFailure():
            raise (self.result.value or self.result.type)
        return self.result
    def _generate(self):
        """ update the active and result member variables """ 
        try:
            self.result = self._next()
            self.stop = 0
        except StopIteration:
            self.stop = 1
            self.result = None
        except Cooperate, coop:
            self.stop = 0
            self.result = coop
        except failure.Failure, fail:
            self.stop = 1
            self.result = failure
        except:
            self.stop = 1
            self.result = failure.Failure()

class Flow:
    """ A flow contruct, created with a top-level generator/iterator

        The iterable provided to this flow is the top-level consumer
        object.  From within the consumer, multiple 'yield' calls can
        be made returning either Cooperate or Generate.  If a Generate
        object is returned, then it becomes the current context and
        the process is continued.  Communication from the producer 
        back to the consumer is done by yield of a non FlowItem
    """
    def __init__(self, iterable):
        self.results = []
        self._stack  = [Generator(iterable)]
    def _addResult(self, result):
        """ private called as top-level results are added"""
        self.results.append(result)
    def _execute(self):
        """ private execute, execute flow till a Cooperate is found """
        while self._stack:
            head = self._stack[-1]
            head._generate()
            if head.stop:
                self._stack.pop()
            else:
                result = head.result
                if isinstance(result, FlowCommand):
                    if isinstance(result, Cooperate):
                        return result.timeout
                    assert(isinstance(result, Generator))
                    self._stack.append(result)
                else:
                    if len(self._stack) > 1:
                        self._stack.pop()
                    else:
                        if self._addResult(result):
                            return
    def execute(self):
        """ continually execute, using sleep for Cooperate """
        from time import sleep
        while 1:
            timeout = self._execute()
            if timeout is None: break
            sleep(timeout)

from twisted.internet import defer
class DeferredFlow(Flow, defer.Deferred):
    """ a version of Flow using Twisted's reactor and Deferreds
 
        In this version, a call to execute isn't required.  Instead,
        the iterable is scheduled right away using the reactor.  And,
        the Cooperate is implemented through the reactor's callLater.
 
        Since more than one (possibly failing) result could be returned,
        this uses the same semantics as DeferredList
    """
    def __init__(self, iterable, delay = 0, 
                 fireOnOneCallback=0, fireOnOneErrback=0):
        """initialize a DeferredFlow
        @param iterable:          top level iterator / generator
        @param delay:             delay when scheduling reactor.callLater
        @param fireOnOneCallback: a flag indicating that the first good 
                                  yielded result should be sent via Callback
        @param fireOnOneErrback:  a flag indicating that the first failing
                                  yield result should be sent via Errback
        """
        from twisted.internet import reactor
        defer.Deferred.__init__(self)
        Flow.__init__(self,iterable)
        self.fireOnOneCallback = fireOnOneCallback
        self.fireOnOneErrback  = fireOnOneErrback
        reactor.callLater(delay, self._execute)
    def execute(self): 
        raise TypeError("Deferred Flow is auto-executing") 
    def _addResult(self, result):
        """ emulate DeferredList behavior, short circut if event is fired """
        if not self.called:
            if self.fireOnOneCallback:
                if not isinstance(result, failure.Failure):
                    self.callback((result,len(self.results)))
                    return 1
            if self.fireOnOneErrback:
                if isinstance(result, failure.Failure):
                    self.errback(fail.Failure((result,len(self.results))))
                    return 1
            self.results.append(result)
    def _execute(self):
        timeout = Flow._execute(self)
        if timeout is None:
            if not self.called:
                self.callback(self.results)
        else:
            from twisted.internet import reactor
            reactor.callLater(timeout, self._execute)
 
#
# The following is a thread package which really is othogonal to
# Flow.  Flow does not depend on it, and it does not depend on Flow.
# Although, if you are trying to bring the output of a thread into
# a Flow, it is exactly what you want.   The QueryIterator is 
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
                self.isFinished = 0
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
                    self.failure = failure.Failure()
                from twisted.internet.reactor import callFromThread
                try:
                    while 1:
                        val = self.source.next()
                        if self.extend:
                            self.buff.extend(val)
                        else:
                            self.buff.append(val)
                except StopIteration:
                    callFromThread(self.stop)
                except: 
                    if not self.failure:
                        self.failure = failure.Failure()
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
