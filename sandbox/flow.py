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
    types of yield statements:  flow.Cooperate, flow.Wrap, or
    any other return value with exceptions wrapped using failure.Failure
    An example program...

        from __future__ import generators
        import flow
        def producer():
            lst = flow.Wrap([1,2,3])
            nam = flow.Wrap(['one','two','three'])
            while 1:
                yield lst; yield nam
                if lst.stop or nam.stop: 
                    return
                yield (lst.result, nam.result)
    
        def consumer():
            title = flow.Wrap(['Title'])
            yield title
            print title.getResult()
            lst = flow.Wrap(producer())
            try:
                while 1:
                    yield lst
                    print lst.getResult()
            except flow.StopIteration: pass
    
        for x in flow.Iterator(consumer()):
            print x
    
    produces the output:

        Title
        (1, 'one')
        (2, 'two')
        (3, 'three')
        
"""
from twisted.python import failure
from twisted.python.compat import StopIteration, iter

class Cooperate:
    """ Represents a request to delay and let other events process

        Objects of this type are returned within a flow when
        the flow would block, or needs to sleep.  This object
        is then used as a signal to the flow mechanism to pause
        and perhaps let other delayed operations to proceed.
    """
    def __init__(self, timeout = 0):
        self.timeout = timeout

class Command: 
    """ Flow control commands which are returned with a yield statement

        After a Command has been subject to a yield, and control has
        returned to the caller, the object will have two attributes:

            stop    This is true if the underlying generator has 
                    finished execution (raised a StopIteration or returned)

            result  This is the result of the generator if it is active, 
                    the result may be a fail.Failure object if an 
                    exception was thrown in the nested generator.
    """      
    def __init__(self):
        self.result = None
        self.stop   = 0
    def isFailure(self):
        """ return a boolean value if the result is a Failure """ 
        return isinstance(self.result, failure.Failure)
    def getResult(self):
        """ return the result, or re-throw an exception on Failure """
        if self.stop: raise StopIteration()
        if self.isFailure(): 
            self.result.trap()
        return self.result
    def _next(self):
        """ execute one iteration

            This method is private within the scope of the flow
            module, it is used by one stage in the flow to ask
            for the next stage to produce.   If a value is 
            returned, then it shall be passed all the way up
            the call chain (useful for Cooperate) without 
            changing the execution path.
        """
        pass

class Wrap(Command):
    """ Wraps a generator or other iterator for use in a flow 

        Creates a nested generation stage (a producer) which can provide
        zero or more values to the current stage (the consumer).
    """      
    def __init__(self, iterable):
        Command.__init__(self)
        try:
            self._wrapped_next = iter(iterable).next
        except TypeError:
            iterable = iterable()
            self._wrapped_next = iter(iterable).next
        self._next_stage  = None
        self._stop_next = 0
    def _next(self):
        """ See Command._next()

            To fetch the next value, the Wrap command first checks to 
            see if there is a next stage which must be processed first.  
            If so, it does that.   Note that the next stage does not need
            to be remembered, as the current stage will yield the same 
            object again if requires further processing.

            After this, it calles the wrapped generator's next method,
            and process the result.   If the result is a Command, then
            this is queued for execution.  Otherwise, either Cooperate
            object is returned, or None is returned indicating that
            a result was produced.
        """
        self.result = None
        if self._stop_next or self.stop:
            self.stop = 1
            return
        while 1:
            next = self._next_stage
            if next:
                result = next._next()
                if result: return result
                self._next_stage = None 
            try:
                result = self._wrapped_next()
                if isinstance(result, Command):
                    self._next_stage = result
                    continue
                if isinstance(result, Cooperate):
                    return result
                self.result = result
            except Cooperate, coop: 
                return coop
            except StopIteration:
                self.stop = 1
            except failure.Failure, fail:
                self.result = fail
                self._stop_next = 1
            except:
                self.result = failure.Failure()
                self._stop_next = 1
            return

class Merge(Command):
     """ Merges two or more Commands into a single stream """
     pass

class Iterator:
    """ Converts a Command into an Iterator

        This converts a Command into the Iterator interface for 
        use in situation where blocking for the next value is
        acceptable.   Basically, it wraps any iterator/generator
        as a Command object, and then eats any Cooperate results.

        This is largely helpful for testing or within a threaded
        environment.

    """
    def __init__(self, command, failureAsResult = 0, shouldBlock = 1 ):
        """initialize a Flow
        @param command:         top level iterator or command
        @param failureAsResult  if true, then failures will be added to 
                                the result list provided to the callback,
                                otherwise the first failure results in 
                                the errback being called with the failure.
        """
        self.shouldBlock           = shouldBlock
        self.failureAsResult = failureAsResult
        if not isinstance(command, Command):
            command = Wrap(command)
        self._command = command
    def __iter__(self):
        return self
    def next(self):
        """ fetch the next value from the Command flow """
        cmd = self._command
        if cmd.stop: raise StopIteration
        result = cmd._next()
        if result:
            if isinstance(result, Cooperate):
                if self.shouldBlock:
                    from time import sleep
                    sleep(result.timeout)
                else:
                    return result
            raise TypeError("Invalid command result")
        if self.failureAsResult: 
            return cmd.result
        else:
            return cmd.getResult()

from twisted.internet import defer
class Deferred(defer.Deferred):
    """ wraps up a Command with a Deferred interface
 
        In this version, the results of the Command are used to 
        construct a list of results and then sent to deferred.  Further,
        in this version Cooperate is implemented via reactor's callLater.
    """
    def __init__(self, command, failureAsResult = 0, delay = 0 ):
        """initialize a DeferredFlow
        @param iterable:        top level iterator / generator
        @param delay:           delay when scheduling reactor.callLater
        @param failureAsResult  if true, then failures will be added to 
                                the result list provided to the callback,
                                otherwise the first failure results in 
                                the errback being called with the failure.
        """
        defer.Deferred.__init__(self)
        self.failureAsResult = failureAsResult
        self._results = []
        if not isinstance(command, Command):
            command = Wrap(command)
        self._command = command
        from twisted.internet import reactor
        reactor.callLater(delay, self._execute)
    def _execute(self):
        cmd = self._command
        while 1:
            result = cmd._next()
            if cmd.stop:
                if not self.called:
                    self.callback(self._results)
                return
            if result:
                if isinstance(result, Cooperate):
                    from twisted.internet import reactor
                    reactor.callLater(result.timeout, self._execute)
                    return
                raise TypeError("Invalid command result")
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
