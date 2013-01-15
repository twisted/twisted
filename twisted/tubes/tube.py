# -*- test-case-name: twisted.tubes.test.test_tube -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
See L{Tube}.
"""

from zope.interface import implements

from twisted.tubes.itube import IDrain
from twisted.tubes.itube import IFount

class Tube(object):
    """
    A L{Tube} is an L{IDrain} and possibly also an L{IFount}, and provides lots
    of conveniences to make it easy to implement something that does fancy flow
    control with just a few methods.

    @ivar drain: the implementation of the L{IFount.drain} attribute.  The
        L{IDrain} to which this L{Tube}'s L{IFount} implementation is flowing.

    @ivar fount: the implementation of the L{IDrain.fount} attribute.  The
        L{IFount} which is flowing to this L{Tube}'s L{IDrain} implementation.

    @ivar valve: the L{Valve} which will receive values from this tube and call
        C{deliver} to deliver output to it.  (When set, this will automatically
        set the C{tube} attribute of said L{Valve} as well, as well as
        un-setting the C{tube} attribute of the old valve.)

    @ivar _currentlyPaused: is this L{Tube} currently paused?  Boolean: C{True}
        if paused, C{False} if not.  This variable tracks whether this L{Tube}
        has invoked L{pauseFlow} on I{its} C{fount} attribute, so it may only
        be set if the fount has also been set (by calling
        C{otherFount.flowTo(thisTube)}).
    """

    implements(IDrain, IFount)

    fount = None
    drain = None

    _currentlyPaused = False
    _delivered = False
    _valve = None

    def __init__(self, valve):
        """
        Initialize this L{Tube} with the given L{Valve} to control its
        behavior.
        """
        self._pendingOutput = []
        self.valve = valve


    def _get_valve(self):
        return self._valve


    def _set_valve(self, newValve):
        if self._valve is not None:
            self._valve.tube = None
        self._valve = newValve
        self._valve.tube = self

    valve = property(_get_valve, _set_valve)


    @property
    def inputType(self):
        return self.valve.inputType


    @property
    def outputType(self):
        return self.valve.outputType


    def flowingFrom(self, fount):
        """
        This tube will now have 'receive' called.
        """
        self.valve.started() # XXX testme
        ot = fount.outputType
        it = self.inputType
        if ot is not None and it is not None and not it.isOrExtends(ot):
            raise TypeError()
        self.fount = fount
        return self


    def flowTo(self, drain):
        """
        Flow data from this tube to the given drain.
        """
        self.drain = drain
        # TODO: test for ordering
        result = self.drain.flowingFrom(self)
        for item in self._pendingOutput: # XXX should consumes safely
            self.drain.receive(item)
        return result


    def pauseFlow(self):
        """
        Pause the flow from the fount, or remember to do that when the
        fount is attached, if it isn't yet.
        """
        if self.fount is None:
            self._shouldPauseWhenStarted = True
        else:
            self._currentlyPaused = True
            self.fount.pauseFlow()


    def resumeFlow(self):
        """
        Resume the flow from the fount to this L{Tube}.
        """
        self.fount.resumeFlow()


    def isFlowing(self):
        """
        Is this flowing?
        """
        if self.fount is None:
            return False
        return self.fount.isFlowing()


    def receive(self, item):
        """
        An item was received.  Subclasses should override to process it.
        """
        result = self.valve.received(item)
        if result is None:
            # postel principle, let valves be as lax as possible
            result = 0.5
        if self.drain is not None:
            if not self._delivered:
                self.drain.progress()
            else:
                self._delivered = False
        return result


    def progress(self, amount=None):
        """
        Progress was made.
        """
        self.valve.progressed(amount)


    def deliver(self, item):
        """
        Deliver the given item to this L{Tube}'s C{drain} attribute, if it has
        yet been set by L{flowingFrom}.
        """
        self._delivered = True
        if self.drain is None:
            self._pendingOutput.append(item)
            return 1.0
        else:
            return self.drain.receive(item)



class Valve(object):
    """
    Helper / null implementation for L{IValve}.  You can inherit from this to
    get no-op implementation of all of L{IValve}'s required implementation so
    you can just just implement the parts you're interested in.

    @ivar tube: the L{Tube} whose flow this valve is controlling.  This
        attribute will be set before 'started' is called.

    @ivar inputType: The type of data expected to be received by C{receive}.

    @ivar outputType: The type of data expected to be emitted to
        C{self.tube.deliver}.
    """

    inputType = None
    outputType = None
    tube = None

    def started(self):
        """
        @see: L{IValve.started}
        """


    def received(self, item):
        """
        @see: L{IValve.received}
        """


    def progressed(self, amount=None):
        """
        @see: L{IValve.progressed}
        """


    def stopped(self, reason):
        """
        @see: L{IValve.stopped}
        """


