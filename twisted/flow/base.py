# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Author: Clark Evans  (cce@clarkevans.com)
#
"""
flow.base

This module contains the core exceptions and base classes in the flow module.
See flow.flow for more detailed information
"""

import twisted.python.compat
from twisted.internet import reactor
import time

#
# Exceptions used within flow
# 
class Unsupported(NotImplementedError):
    """ Indicates that the given stage does not know what to do 
        with the flow instruction that was returned.
    """
    def __init__(self, inst):
        msg = "Unsupported flow instruction: %s " % repr(inst)
        TypeError.__init__(self,msg)

class NotReadyError(RuntimeError):
    """ Raised when a stage has not been subject to a yield """
    pass

#
# Abstract/Base Classes
#

class Instruction:
    """ Has special meaning when yielded in a flow """
    pass
 
class Controller:
    """
    Flow controller

    At the base of every flow, is a controller class which interprets the
    instructions, especially the CallLater instructions.  This is primarly just
    a marker class to denote which classes consume Instruction events.  If a
    controller cannot handle a particular instruction, it raises the
    Unsupported exception.
    """
    pass

class CallLater(Instruction):
    """
    Instruction to support callbacks

    This is the instruction which is returned during the yield of the _Deferred
    and Callback stage.  The underlying flow driver should call the 'callLater'
    function with the callable to be executed after each callback.
    """
    def callLater(self, callable):
        pass

class Cooperate(CallLater):
    """
    Requests that processing be paused so other tasks can resume

    Yield this object when the current chain would block or periodically during
    an intensive processing task.  The flow mechanism uses these objects to
    signal that the current processing chain should be paused and resumed
    later.  This allows other delayed operations to be processed, etc.  Usage
    is quite simple::

       # within some generator wrapped by a Controller
       yield Cooperate(1)  # yield for a second or more

    """
    def __init__(self, timeout = 0):
        self.timeout = timeout
    def callLater(self, callable):
        reactor.callLater(self.timeout, callable)

class Stage(Instruction):
    """
    Abstract base defining protocol for iterator/generators in a flow

    This is the primary component in the flow system, it is an iterable object
    which must be passed to a yield statement before each call to next().
    Usage::

       iterable = DerivedStage( ... , SpamError, EggsError))
       yield iterable
       for result in iterable:
           # handle good result, or SpamError or EggsError
           yield iterable

    Alternatively, when inside a generator, the next() method can be used
    directly.  In this case, if no results are available, StopIteration is
    raised, and if left uncaught, will nicely end the generator.  Of course,
    unexpected failures are raised.  This technique is especially useful when
    pulling from more than one stage at a time.  For example::

         def someGenerator():
             iterable = SomeStage( ... , SpamError, EggsError)
             while True:
                 yield iterable
                 result = iterable.next()
                 # handle good result or SpamError or EggsError

    For many generators, the results become available in chunks of rows.  While
    the default value is to get one row at a time, there is a 'chunked'
    property which allows them to be returned via the next() method as many
    rows rather than row by row.  For example::

         iterable = DerivedStage(...)
         iterable.chunked = True
         for results in iterable:
             for result in results:
                  # handle good result
             yield iterable

    For those wishing more control at the cost of a painful experience, the
    following member variables can be used to great effect::

        - results: This is a list of results produced by the generator, they
                   can be fetched one by one using next() or in a group
                   together.  If no results were produced, then this is an
                   empty list.  These results should be removed from the list
                   after they are read; or, after reading all of the results
                   set to an empty list

        - stop: This is true if the underlying generator has finished execution
                (raised a StopIteration or returned).  Note that several
                results may exist, and stop may be true.

        - failure: If the generator produced an exception, then it is wrapped
                   as a Failure object and put here.  Note that several results
                   may have been produced before the failure.  To ensure that
                   the failure isn't accidently reported twice, it is
                   adviseable to set stop to True.

    The order in which these member variables is used is *critical* for
    proper adherance to the flow protocol.   First, all successful
    results should be handled.  Second, the iterable should be checked
    to see if it is finished.  Third, a failure should be checked;
    while handling a failure, either the loop should be exited, or
    the iterable's stop member should be set.  For example::

         iterable = SomeStage(...)
         while True:
             yield iterable
             if iterable.results:
                 for result in iterable.results:
                     # handle good result
                 iterable.results = []
             if iterable.stop:
                 break
             if iterable.failure:
                 iterable.stop = True
                 # handle iterable.failure
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
        """
        return current result

        This is the primary function to be called to retrieve the current
        result.  It complies with the iterator protocol by raising
        StopIteration when the stage is complete.  It also raises an exception
        if it is called before the stage is yielded.
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

            cr = self.failure.check(*self._trap)

            if cr:
                return cr

            self.failure.raiseException()

        raise NotReadyError("Must 'yield' this object before calling next()")

    def _yield(self):
        """
        executed during a yield statement by previous stage

        This method is private within the scope of the flow module, it is used
        by one stage in the flow to ask a subsequent stage to produce its
        value.  The result of the yield is then stored in self.result and is an
        instance of Failure if a problem occurred.
        """
        raise NotImplementedError
