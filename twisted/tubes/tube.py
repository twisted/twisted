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

    @ivar pump: the L{Pump} which will receive values from this tube and call
        C{deliver} to deliver output to it.  (When set, this will automatically
        set the C{tube} attribute of said L{Pump} as well, as well as
        un-setting the C{tube} attribute of the old pump.)

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
    _pump = None

    def __init__(self, pump):
        """
        Initialize this L{Tube} with the given L{Pump} to control its
        behavior.
        """
        self._pendingOutput = []
        self.pump = pump


    def _get_pump(self):
        return self._pump


    def _set_pump(self, newPump):
        if self._pump is not None:
            self._pump.tube = None
        self._pump = newPump
        self._pump.tube = self

    pump = property(_get_pump, _set_pump)


    @property
    def inputType(self):
        return self.pump.inputType


    @property
    def outputType(self):
        return self.pump.outputType


    def flowingFrom(self, fount):
        """
        This tube will now have 'receive' called.
        """
        self.pump.started() # XXX testme
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


    def flowStopped(self, reason):
        """
        This tube has now stopped.
        """
        self.pump.stopped(reason)


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


    def stopFlow(self):
        """
        Stop the flow from the fount to this L{Tube}.
        """
        self.fount.stopFlow()


    def receive(self, item):
        """
        An item was received.  Subclasses should override to process it.
        """
        result = self.pump.received(item)
        if result is None:
            # postel principle, let pumps be as lax as possible
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
        self.pump.progressed(amount)


    def deliver(self, item):
        """
        Deliver the given item to this L{Tube}'s C{drain} attribute, if it has
        yet been set by L{flowingFrom}.
        """
        self._delivered = True
        if self.drain is None:
            if self.fount is not None:
                self.fount.pauseFlow()
            self._pendingOutput.append(item)
            return 1.0
        else:
            return self.drain.receive(item)



class Pump(object):
    """
    Null implementation for L{IPump}.  You can inherit from this to
    get no-op implementation of all of L{IPump}'s required implementation so
    you can just just implement the parts you're interested in.

    @ivar tube: The L{Tube} whose flow this pump is controlling.  This
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
        @see: L{IPump.started}
        """


    def received(self, item):
        """
        @see: L{IPump.received}
        """


    def progressed(self, amount=None):
        """
        @see: L{IPump.progressed}
        """


    def stopped(self, reason):
        """
        @see: L{IPump.stopped}
        """
