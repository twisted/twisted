# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Author: Clark Evans
# 
 
""" flow.wrap 

    This module provides the wrap() function in the flow module and
    the private classes used for its implementation.
"""

from base import *
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred

class _String(Stage):
    """ Wrapper for a string object; don't create directly use flow.wrap

        This is probably the simplest stage of all.  It is a 
        constant list of one item.   See wrap for an example.

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

class _DeferredInstruction(CallLater):
    def __init__(self, deferred):
        self.deferred = deferred
    def callLater(self, callable):
        self.deferred.addBoth(callable)

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
                if isinstance(result, Deferred):
                    if result.called:
                        continue
                    return _DeferredInstruction(result)
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
    def __init__(self, deferred, *trap):
        Stage.__init__(self, *trap)
        self._called     = False
        deferred.addCallbacks(self._callback, self._errback)
        self._cooperate  = _DeferredInstruction(deferred)

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
        if self._called:
           self.stop = True
           return

def wrap(obj, *trap):
    """
    Wraps various objects for use within a flow

    The following example illustrates many different ways in which regular
    objects can be wrapped by the flow module to behave in a cooperative
    manner.

    For example::

        # required imports
        from __future__ import generators
        from twisted.flow import flow
        from twisted.internet import reactor, defer

        # save this function, it is used everwhere
        def printFlow(source):
            def printer(source):
                source = flow.wrap(source)
                while True:
                    yield source
                    print source.next()
            d = flow.Deferred(printer(source))
            d.addCallback(lambda _: reactor.stop())
            reactor.run()

        source = "string"
        printFlow(source)

        source = ["one",flow.Cooperate(1),"two"]
        printFlow(source)

        def source():
            yield "aeye"
            yield flow.Cooperate()
            yield "capin"
        printFlow(source)

        source = Deferred()
        reactor.callLater(1, lambda: source.callback("howdy"))
        printFlow(source)

    """
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

    if isinstance(obj, Deferred):
        return _Deferred(obj, *trap)

    try:
        return _Iterable(obj, *trap)
    except TypeError: 
        pass

    raise ValueError, "A wrapper is not available for %r" % (obj,)

