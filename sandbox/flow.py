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
''' Flow -- async data flow

    This module provides a mechanism for using async data flows through
    the use of generators.  While this module does not use generators in
    its implementation, it isn't very useable without them.

    A data flow starts with a top level generator, which has numerous
    yield statements.   Each yield can return one of several types:

        flow.Cooperate  This (singleton) value should be returned when 
                        the flow would like to give up control of the 
                        call stack to allow other events to be handled.

        flow.Generator  This is a sub-flow (iterator) to be executed.  
                        This object has a 'result' value which can be 
                        checked for each value yielded.   If the last
                        iteration of the sub-flow produced an exception,
                        then a failure.Failure object will be returned.

                        While the sub-flow is generating (it has not
                        returned or raised StopIteration), it will have
                        an 'active' state of true.  Once it is finished,
                        the 'active' state will be false.

       <anything>       Any other return value, which is not a FlowItem
 
'''
from __future__ import nested_scopes
from twisted.python import failure
from twisted.python.compat import StopIteration, iter

class FlowItem: pass
Cooperate = FlowItem() 

class Generator(FlowItem):
    def __init__(self, iterable):
        self.__next  = iter(iterable).next
        self.result  = None
        self.active  = 1
    def isFailure(self):
        return isinstance(self.result, failure.Failure)
    def getResult(self):
        if self.isFailure():
            res = self.result
            if res.value:  raise res.value
            raise res.type
        return self.result
    def generate(self):
        try:
            self.result = self.__next()
        except StopIteration:
            self.active = 0
            self.result = None
        except:
            self.active = 0
            self.result = failure.Failure()

class Flow(Generator):
    ''' a top-level generator which can handle subordinates '''
    def __init__(self, iterable):
        Generator.__init__(self, iterable)
        self._stack = [self]
    def execute(self, cooperate = 0):
        while self._stack:
            head = self._stack[-1]
            head.generate()
            if head.active:
                if isinstance(result, FlowItem):
                    if result is Cooperate:
                        if cooperate: return 1
                    self._stack.append(result)
            else:
                self._stack.pop()
                
#
# This code below belongs in twisted.internet.defer
#

from twisted.internet import defer, reactor
class DeferredFlow(Flow, defer.Deferred):
   ''' a version of Flow using Twisted's reactor and Deferreds '''
   def __init__(self, iterable):
       defer.Deferred.__init__(self)
       Flow.__init__(iterable)
       reactor.callLater(0, self.execute)
   def execute(self):
       if Flow.execute(self, cooperate = 1):
           reactor.callLater(0, self.execute)
       else:
           if self.isFailure():
               self.errback(self.result)
           else:
               self.callback(self.result)

#
# The following is a thread package which really is othogonal to
# Flow.  Flow does not depend on it, and it does not depend on Flow,
# with the exception of 'Cooperate'.  Although, if you are trying 
# to bring the output of a thread into a Flow, it is exactly what 
# you want.   The QueryIterator is just an obvious application 
# of the ThreadedIterator.
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
        raise Cooperation

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
