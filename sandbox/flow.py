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
# Author: Clark Evans  (cce@clarkevans.com)
# 
#
from __future__ import nested_scopes

""" Flow -- asynchronous data flows using generators

    This module provides a mechanism for using async data flows through
    the use of generators.  The basic idea of flow is that when ever
    you require data from a producer, you yield the producer.  If the
    producer is ready, then you can call producer.next() to fetch the
    incoming data.  Otherwise, the underlying process will suspend the
    operation to try again later.

    Most classes in the flow module an Instruction, either a CallLater
    or a Stage.   A Stage instruction is used to wrap various sorts of
    producers, anything from a simple string to Callback functions.  
    Some stages can be constructed directly, such as Zip, Concurrent,
    Merge, Callback, or Threaded.  But in most cases, in particular
    _String, _List, _Iterable, and _Deferred, state construction is
    handled through the wrap function.  Stages can yield other stages 
    to build a processing chain, results which are returned to the 
    previous stage, or a CallLater instruction which causes the whole 
    operation to be suspended.   

    Typically, the CallLater instructions as passed up the call stack
    till the top level, or Controller.  The controller then typically
    returns control, but registers itself to be called later.  Once
    called again, the controller sets up the call stack and resumes
    the top level generator.  There is a special CallLater, Cooperate,
    which simply resumes the chain of stages at a later time.   Some 
    stages, Callback, _Deferred, and Threaded have their own special 
    CallLater which handles the process of resuming flow for their 
    specific case.

    Instruction
       CallLater
          Cooperate
       Stage
              # private stages (use flow.wrap)
          _String
          _List
          _Iterable
          _Deferred
              # public stages
          Zip
          Concurrent
             Merge
          Block
          Callback*
          Threaded*
    Controller
        Deferred 
        Block
        Protocol
"""

import time, types
from twisted.python.failure import Failure
from twisted.python.compat import StopIteration, iter, isinstance, True, False
from twisted.internet import defer, reactor, protocol
from twisted.internet.error import ConnectionLost

#
# Exceptions used within flow
# 
class Unsupported(TypeError):
    """ Indicates that the given stage does not know what to do 
        with the flow instruction that was returned.
    """
    def __init__(self, inst):
        msg = "Unsupported flow instruction: %s " % repr(inst)
        TypeError.__init__(self,msg)

class NotReadyError(RuntimeError):
    """ Used for the default stage value indicating that 'yield' was
        not used on the stage prior to calling it's next() method
        or accessing its 'result' variable.
    """
    pass

#
# Abstract/Base Classes
#

class Instruction:
    """ Has special meaning when yielded in a flow """
    pass
 
class Controller:
    """ Flow controller

        At the base of every flow, is a controller class which 
        interprets the instructions, especially the CallLater 
        instructions.  This is primarly just a marker class to
        denote which classes consume Instruction events.  If a
        controller cannot handle a particular instruction, it
        raises the Unsupported exception.
    """
    pass

class CallLater(Instruction):
    """ Instruction to support callbacks

        This is the instruction which is returned during the yield
        of the _Deferred and Callback stage.   The underlying 
        flow driver should call the 'callLater' function with the 
        callable to be executed after each callback.
    """
    def callLater(self, callable):
        pass

class Cooperate(CallLater):
    """ Requests that processing be paused so other tasks can resume

        Yield this object when the current chain would block or periodically
        during an intensive processing task.   The flow mechanism uses these
        objects to signal that the current processing chain should be paused
        and resumed later.  This allows other delayed operations to be
        processed, etc.
    """
    def __init__(self, timeout = 0):
        self.timeout = timeout
    def callLater(self, callable):
        reactor.callLater(self.timeout, callable)

class Stage(Instruction):
    """ Abstract base defining protocol for iterator/generators in a flow

        This is the primary component in the flow system, it is an
        iterable object which must be passed to a yield statement 
        before each call to next().   Usage...

           iterable = DerivedStage( ... , SpamError, EggsError))
           yield iterable
           for result in iterable:
               // handle good result, or SpamError or EggsError
               yield iterable 

        Alternatively, when inside a generator, the next() method can be
        used directly.   In this case, if no results are available,
        StopIteration is raised, and if left uncaught, will nicely end
        the generator.   Of course, unexpected failures are raised.  This 
        technique is especially useful when pulling from more than 
        one stage at a time.

             def someGenerator():
                 iterable = SomeStage(..., SpamError, EggsError)
                 while True:
                     yield iterable
                     result = iterable.next() 
                     // handle good result or SpamError or EggsError

        For many generators, the results become available in chunks
        of rows.  While the default value is to get one row at a time,
        there is a 'chunked' property which allows them to be 
        returned via the next() method as many rows rather than
        row by row.

             iterable = DerivedStage(...)
             iterable.chunked = 1
             for results in iterable:
                 for result in results:
                      // handle good result
                 yield iterable

        For those wishing more control at the cost of a painful experience,
        the following member variables can be used to great effect:

            results  This is a list of results produced by the generator,
                     they can be fetched one by one using next() or in a
                     group together.  If no results were produced, then
                     this is an empty list.   These results should be 
                     removed from the list after they are read; or, after
                     reading all of the results set to an empty list

            stop     This is true if the underlying generator has finished 
                     execution (raised a StopIteration or returned).  Note
                     that several results may exist, and stop may be true.

            failure  If the generator produced an exception, then it is 
                     wrapped as a Failure object and put here.  Note that
                     several results may have been produced before the 
                     failure.  To ensure that the failure isn't accidently
                     reported twice, it is adviseable to set stop to True.

        The order in which these member variables is used is *critical* for
        proper adherance to the flow protocol.   First, all successful
        results should be handled.  Second, the iterable should be checked
        to see if it is finished.  Third, a failure should be checked; 
        while handling a failure, either the loop should be exited, or
        the iterable's stop member should be set. 

             iterable = SomeStage(...)
             while True:
                 yield iterable
                 if iterable.results:
                     for result in iterable.results:
                         // handle good result
                     iterable.results = []
                 if iterable.stop:
                     break
                 if iterable.failure:
                     iterable.stop = True
                     // handle iterable.failure
                     break
    """      
    def __init__(self, *trap):
        self._trap = trap
        self.stop = False
        self.failure = None
        self.results = []
        self.chunked = False
    
    def __iter__(self):
        return self

    def next(self):
        """ return current result

            This is the primary function to be called to retrieve
            the current result.  It complies with the iterator 
            protocol by raising StopIteration when the stage is
            complete.   It also raises an exception if it is 
            called before the stage is yielded. 
        """
        if self.results:
            if self.chunked:
                ret = self.results
                self.results = []
                return ret
            else:
                return self.results.pop(0)
        if self.stop:
            raise StopIteration()
        if self.failure:
            self.stop = True
            return self.failure.trap(*self._trap)
        raise NotReadyError("Must 'yield' this object before calling next()")

    def _yield(self):
        """ executed during a yield statement by previous stage

            This method is private within the scope of the flow module, 
            it is used by one stage in the flow to ask a subsequent
            stage to produce its value.  The result of the yield is 
            then stored in self.result and is an instance of Failure
            if a problem occurred.
        """
        raise NotImplementedError

#
# Concrete Private Stages
#

class _String(Stage):
    """ Wrapper for a string object; don't create directly use flow.wrap

        This is probably the simplest stage of all.  It is a 
        constant list of one item.   While it may not have much
        pratical use, it is illustrative.
    """
    def __init__(self, str):
        Stage.__init__(self)
        self.results.append(str)
        self.stop = True
    def _yield(self):
        pass

class _List(Stage):
    """ Wrapper for lists and tuple objects; don't create directly

        A simple stage, which admits the usage of instructions,
        such as Cooperate() within the list.   This would be
        much simpler without logic to handle instructions.
    """
    def __init__(self, seq):
        Stage.__init__(self)
        self._seq = list(seq)
    def _yield(self):
        seq = self._seq
        while seq:
            result = seq.pop(0)
            if isinstance(result, Instruction):
                return result
            self.results.append(result)
        self.stop = True

class _Iterable(Stage):
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
        self._next = None

    def _yield(self):
        """ executed during a yield statement """
        if self.results or self.stop or self.failure:
            return
        while True:
            next = self._next
            if next:
                instruction = next._yield()
                if instruction: 
                    return instruction
                self._next = None 
            try:
                result = self._iterable.next()
                if isinstance(result, Instruction):
                    if isinstance(result, Stage):
                        self._next = result
                        continue
                    return result
                self.results.append(result)
            except StopIteration:
                self.stop = True
            except Failure, fail:
                self.failure = fail
            except:
                self.failure = Failure()
            return

class _Deferred(Stage):
    """ Wraps a Deferred object into a stage; create with flow.wrap

        This stage provides a callback 'catch' for errback and
        callbacks.  If not called, then this returns an Instruction
        which will let the reactor execute other operations, such
        as the producer for this deferred.
    """
    class Instruction(CallLater):
        def __init__(self, deferred):
            self.deferred = deferred
        def callLater(self, callable):
            self.deferred.addBoth(callable)
    def __init__(self, deferred, *trap):
        Stage.__init__(self, *trap)
        deferred.addCallbacks(self._callback)
        self._cooperate  = _Deferred.Instruction(deferred)
        self._called     = False
        self._fetched    = False

    def _callback(self, res):
        self._called = True
        self.results = [res]

    def _errback(self, fail):
        self._called = True
        self.failure = fail

    def _yield(self):
        if self.results or self.stop or self.failure:
            return
        if not self._called:
            return self._cooperate
        if self._fetched:
           self.stop = True
           return
        self._fetched = True

def wrap(obj, *trap):
    """ Wraps various objects for use within a flow """
    if isinstance(obj, Stage):
        if trap:
            # merge trap list
            trap = list(trap)
            for ex in obj._trap:
                if ex not in trap:
                    trap.append(ex)
            obj._trap = tuple(trap)
        return obj

    if callable(obj):
        obj = obj()

    typ = type(obj)
    if typ is type([]) or typ is type(tuple()):
        return _List(obj)
    if typ is type(''):
        return _String(obj)
     
    if isinstance(obj, defer.Deferred):
        return _Deferred(obj, *trap)

    try:
        return _Iterable(obj, *trap)
    except TypeError: 
        pass

    raise ValueError, "A wrapper is not available for %r" % (obj,)

#
# Public Stages
# 

class Zip(Stage):
    """ Zips two or more stages into a stream of N tuples

        Zip([1, Cooperate(), 2],[3, 4]) => [ (1, 3), (2, 4) ]

    """
    def __init__(self, *stages):
        Stage.__init__(self)
        self._stage  = []
        for stage in stages:
            self._stage.append(wrap(stage))
        self._index  = 0

    def _yield(self):
        if self.results or self.stop or self.failure:
            return
        if not self._index:
            self._curr = []
        while self._index < len(self._stage):
            idx = self._index
            curr = self._stage[idx]
            instruction = curr._yield()
            if instruction:
                return instruction
            if curr.results:
                self._curr.append(curr.results.pop(0))
                self._index += 1
                continue
            if curr.stop:
                self.stop = True
                return
            if curr.failure:
                self.failure = curr.failure
                return
            self._index += 1
        self.results.append(tuple(self._curr))
        self._index  = 0

class Concurrent(Stage):
    """ Executes stages concurrently

        This stage allows two or more stages (branches) to be executed 
        at the same time.  It returns each stage as it becomes available.
        This can be used if you have N callbacks, and you want to yield 
        and wait for the first available one that produces results.   Once
        a stage is retuned, its next() method should be used to extract 
        the value for the stage.
    """

    class Instruction(CallLater):
        def __init__(self, inst):
            self.inst = inst
        def callLater(self, callable):
            for inst in self.inst:
                inst.callLater(callable)

    def __init__(self, *stages):
        Stage.__init__(self)
        self._stages = []
        for stage in stages:
            self._stages.append(wrap(stage))

    def _yield(self):
        if self.results or self.stop or self.failure:
            return
        stages = self._stages
        coop = None
        later = []
        exit = None
        while stages:
            if stages[0] is exit:
                if self.results:
                    return
                break
            curr = stages.pop(0)
            instruction = curr._yield()
            if curr.results:
                self.results.append(curr)
            if curr.failure:
                self.failure = curr.failure
                return
            if curr.stop:
                exit = None
                if self.results:
                    return
                continue
            stages.append(curr)
            if not exit:
                exit = curr
            if instruction:
                if isinstance(instruction, Cooperate):
                    coop = instruction
                    continue
                if isinstance(instruction, CallLater):
                    later.append(instruction)
                    continue
                raise Unsupported(instruction)
        if later:
            return Concurrent.Instruction(later)
        if coop:
            return coop
        self.stop = True

class Merge(Stage):
    """ Merges two or more Stages results into a single stream

        This Stage can be used for merging two stages into a single
        stage, all while maintaining the ability to pause during Cooperate.
        Note that while this code may be deterministic, applications of
        this module should not depend upon a particular order.   In
        particular, Cooperate events may be ignored or delayed if one
        of the other stages has data available.
    """
    def __init__(self, *stages):
        Stage.__init__(self)
        self.concurrent = Concurrent(*stages)

    def _yield(self):
        if self.results or self.stop or self.failure:
            return
        instruction = self.concurrent._yield()
        if instruction: 
            return instruction
        for stage in self.concurrent.results:
            self.results.extend(stage.results)
            stage.results = []
        self.concurrent.results = []
        if self.concurrent.stop:
            self.stop = True
        self.failure =  self.concurrent.failure

class Callback(Stage):
    """ Converts a single-thread push interface into a pull interface.
   
        Once this stage is constructed, its callback, errback, and 
        finish member variables may be called by a producer.   The
        results of which can be obtained by yielding the Callback and
        then calling next()
    """
    class Instruction(CallLater):
        def __init__(self):
            self.flow = lambda: True
        def callLater(self, callable):
            self.flow = callable
    def __init__(self, *trap):
        Stage.__init__(self, *trap)
        self._finished   = False
        self._cooperate  = Callback.Instruction()
    def result(self,result):
        """ called by the producer to indicate a successful result """
        self.results.append(result)
        self._cooperate.flow()
    def finish(self):
        """ called by producer to indicate successful stream completion """
        assert not self.failure, "failed streams should not be finished"
        self._finished = True
        self._cooperate.flow()
    def errback(self, fail):
        """ called by the producer in case of Failure """
        self.failure = fail
        self._cooperate.flow()
    def _yield(self):
        if self.results or self.stop or self.failure:
            return
        if not self.results: 
            if self._finished:
                self.stop = True
                return
            return self._cooperate
    __call__ = result

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
    class Instruction(CallLater):
        def __init__(self):
            self.flow = None
        def callLater(self, callable):
            self.flow = callable
        def __call__(self):
            if self.flow:
                reactor.callFromThread(self.flow)
                self.flow = None

    def __init__(self, iterable, *trap):
        Stage.__init__(self, trap)
        self._iterable  = iterable
        self._cooperate = Threaded.Instruction()
        self.srcchunked = getattr(iterable, 'chunked', False)
        reactor.callInThread(self._process)

    def _process(self):
        """ pull values from the iterable and add them to the buffer """
        try:
            self._iterable = iter(self._iterable)
        except: 
            self.failure = Failure()
            self._cooperate()
            return
        else:
            try:
                while True:
                    val = self._iterable.next()
                    if self.srcchunked:
                        self.results.extend(val)
                    else:
                        self.results.append(val)
                    self._cooperate()
            except StopIteration:
                pass
            except: 
                self.failure = Failure()
        self.stop = True
        self._cooperate()

    def _yield(self):
        if self.results or self.stop or self.failure:
            return
        return self._cooperate

#
# Public Controllers
#

class Block(Controller,Stage):
    """ A controller which blocks on Cooperate events

        This converts a Stage into an iterable which can be used 
        directly in python for loops and other iteratable constructs.
        It does this by eating any Cooperate values and sleeping.
        This is largely helpful for testing or within a threaded
        environment.  It converts other stages into one which 
        does not emit cooperate events.

        [1,2, Cooperate(), 3] => [1,2,3]

    """
    def __init__(self, stage, *trap):
        Stage.__init__(self)
        self._stage = wrap(stage,*trap)
        self.block = time.sleep

    def next(self):
        """ fetch the next value from the Stage flow """
        stage = self._stage
        while True:
            result = stage._yield()
            if result:
                if isinstance(result, Cooperate):
                    if result.__class__ == Cooperate:
                        self.block(result.timeout)
                        continue
                raise Unsupported(result)
            return stage.next()

class Deferred(Controller, defer.Deferred):
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
    def __init__(self, stage, *trap):
        defer.Deferred.__init__(self)
        self._results = []
        self._stage = wrap(stage, *trap)
        self._execute()

    def results(self, results):
        self._results.extend(results)

    def _execute(self, dummy = None):
        cmd = self._stage
        while True:
            result = cmd._yield()
            if cmd.results:
                self.results(cmd.results)
                cmd.results = []
            if cmd.stop:
                if not self.called:
                    self.callback(self._results)
                return
            if cmd.failure:
                cmd.stop = True
                if cmd._trap:
                    error = cmd.failure.check(*cmd._trap)
                    if error:
                        self._results.append(error)
                        continue
                self.errback(cmd.failure)
                return
            if result:
                if isinstance(result, CallLater):
                    result.callLater(self._execute)
                    return
                raise Unsupported(result)

def makeProtocol(controller, baseClass = protocol.Protocol, 
                  *callbacks, **kwargs):
    """ Construct a flow based protocol

        This takes a base protocol class, and a set of callbacks and
        creates a connection flow based on the two.   For example, 
        the following would build a simple 'echo' protocol.

            PORT = 8392
            def echoServer(conn):
                yield conn
                for data in conn:
                    yield data
                    yield conn
            
            def echoClient(conn):
                yield "hello, world!"
                yield conn
                print "server said: ", conn.next()
                reactor.callLater(0,reactor.stop)
            
            server = protocol.ServerFactory()
            server.protocol = flow.makeProtocol(echoServer)
            reactor.listenTCP(PORT,server)
            client = protocol.ClientFactory()
            client.protocol = flow.makeProtocol(echoClient)
            reactor.connectTCP("localhost", PORT, client)
            reactor.run()

    """
    if not callbacks:
        callbacks = ('dataReceived',)
    class _Protocol(Controller, Callback, baseClass):
        def __init__(self):
            Callback.__init__(self)
            setattr(self, callbacks[0], self)  # only one callback support
        def _execute(self, dummy = None):
            cmd = self._controller
            self.write = self.transport.write
            while True:
                instruction = cmd._yield()
                if instruction:
                    if isinstance(instruction, CallLater):
                        instruction.callLater(self._execute)
                        return
                    raise Unsupported(instruction)
                if cmd.stop:
                    self.transport.loseConnection()
                    return
                if cmd.failure:
                    print "TODO: Help! Any ideas on reporting faliures?"
                    cmd.failure.trap()
                    return
                if cmd.results:
                    self.transport.writeSequence(cmd.results)
                    cmd.results = []
        def connectionMade(self):
            if types.ClassType == type(self.controller):
                self._controller = wrap(self.controller(self))
            else:
                self._controller = wrap(self.controller())
            self._execute()
        def connectionLost(self, reason=protocol.connectionDone):
            if protocol.connectionDone is reason or \
               ( self.finishOnConnectionLost and \
                 isinstance(reason.value, ConnectionLost)):
                self.finish()
            else:
                self.errback(reason)
            self._execute()
    _Protocol.finishOnConnectionLost = kwargs.get("finishOnConnectionLost",True)
    _Protocol.controller = controller
    return _Protocol

def _NotImplController(protocol):
    raise NotImplementedError
Protocol = makeProtocol(_NotImplController) 
Protocol.__doc__ = """ A concrete flow.Protocol for inheritance """

#
# Other (indirectly related) stuff
#

class QueryIterator:
    """ Converts a database query into a result iterator """

    def __init__(self, pool, sql, fetchmany=False, fetchall=False):
        self.curs = None
        self.sql = sql
        self.pool = pool
        if fetchmany: 
            self.next = self.next_fetchmany
            self.chunked = True
        if fetchall:
            self.next = self.next_fetchall
            self.chunked = True

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

