# -*- test-case-name: twisted.tubes.test.test_tube -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
See L{Tube}.
"""

from zope.interface import implementer

from twisted.tubes.itube import IDrain
from twisted.tubes.itube import IPump
from twisted.tubes.itube import IFount


class _TubePiece(object):
    """
    Shared functionality between L{_TubeFount} and L{_TubeDrain}
    """
    def __init__(self, tube):
        self._tube = tube


    @property
    def _pump(self):
        return self._tube.pump



@implementer(IFount)
class _TubeFount(_TubePiece):
    """
    Implementation of L{IFount} for L{_Tube}.

    @ivar fount: the implementation of the L{IDrain.fount} attribute.  The
        L{IFount} which is flowing to this L{_Tube}'s L{IDrain} implementation.

    @ivar drain: the implementation of the L{IFount.drain} attribute.  The
        L{IDrain} to which this L{_Tube}'s L{IFount} implementation is flowing.
    """
    drain = None

    @property
    def outputType(self):
        return self._pump.outputType


    def flowTo(self, drain):
        """
        Flow data from this tube to the given drain.
        """
        self.drain = drain
        wasPaused = self._tube._currentlyPaused
        result = self.drain.flowingFrom(self)
        self._tube._nextFount = result
        if wasPaused:
            self.resumeFlow()
        return result


    def pauseFlow(self):
        """
        Pause the flow from the fount, or remember to do that when the
        fount is attached, if it isn't yet.
        """
        self._tube._currentlyPaused = True
        fount = self._tube._tdrain.fount
        if fount is not None:
            fount.pauseFlow()


    def resumeFlow(self):
        """
        Resume the flow from the fount to this L{_Tube}.
        """
        self._tube._currentlyPaused = False
        fount = self._tube._tdrain.fount
        if fount is not None:
            fount.resumeFlow()
        self._tube._unbufferSome()


    def stopFlow(self):
        """
        Stop the flow from the fount to this L{_Tube}.
        """
        fount = self._tube._tdrain.fount
        fount.stopFlow()



@implementer(IDrain)
class _TubeDrain(_TubePiece):
    """
    Implementation of L{IDrain} for L{_Tube}.
    """
    fount = None

    @property
    def inputType(self):
        return self._pump.inputType


    @property
    def _drain(self):
        return self._tube._tfount.drain


    @property
    def _get_delivered(self):
        return self._tube._tfount.drain


    def flowingFrom(self, fount):
        """
        This tube will now have 'receive' called.
        """
        out = fount.outputType
        in_ = self.inputType
        if out is not None and in_ is not None and not in_.isOrExtends(out):
            raise TypeError()
        self.fount = fount
        if self._tube._pendingOutput:
            self._tube._tfount.pauseFlow()
        self._pump.started()
        nextFount = self._tube._nextFount
        if nextFount is not None:
            return nextFount
        return self._tube._tfount


    def progress(self, amount=None):
        """
        Progress was made.
        """
        self._pump.progressed(amount)


    def receive(self, item):
        """
        An item was received.
        """
        self._tube._pumpReceiving = True
        try:
            result = self._pump.received(item)
        finally:
            self._tube._pumpReceiving = False
        self._tube._unbufferSome()
        if self._tube._switchFlush:
            self._tube._finishSwitching()
        if result is None:
            # postel principle, let pumps be as lax as possible
            result = 0.5
        drain = self._tube._tfount.drain
        if drain is not None:
            if not self._tube._delivered:
                drain.progress()
            else:
                self._delivered = False
        return result


    def flowStopped(self, reason):
        """
        This tube has now stopped.
        """
        self._pump.stopped(reason)



def cascade(start, *plumbing):
    """
    Connect up a series of objects capable of transforming inputs to outputs;
    convert a sequence of L{IPump} objects into a sequence of connected
    L{IFount} and L{IDrain} objects.

    This function can best be understood by understanding that::

        x = a
        a.flowTo(b).flowTo(c)

    is roughly analagous to::

        x = cascade(a, b, c)

    with the additional feature that C{cascade} will convert C{a}, C{b}, and
    C{c} to the requisite L{IDrain} objects first.

    @param start: The initial element in the chain; the object that will
        consume inputs passed to the result of this call to C{cascade}.
    @type start: an L{IPump}, or anything adaptable to L{IFount}, as well as
        L{IDrain}.

    @param plumbing: Each element of C{plumbing}.
    @type plumbing: a L{tuple} of L{IPump}s or objects adaptable to L{IDrain}.

    @return: An L{IDrain} that can consume inputs of C{start}'s C{inputType},
        and whose C{flowingFrom} will return an L{IFount} that will produce
        outputs of C{plumbing[-1]} (or C{start}, if plumbing is empty).
    @rtype: L{IDrain}

    @raise TypeError: if C{start}, or any element of C{plumbing} is not
        adaptable to L{IDrain}.
    """
    with _registry(_pump_registry):
        result = IDrain(start)
        currentFount = IFount(start)
        drains = map(IDrain, plumbing)
    for drain in drains:
        currentFount = currentFount.flowTo(drain)
    return result



def _pumpToTube(pump):
    if pump.tube is not None:
        # XXX how does this even get exercised?
        return pump.tube
    return _Tube(pump)



from zope.interface.adapter import AdapterRegistry
from twisted.python.components import _addHook, _removeHook
from contextlib import contextmanager
@contextmanager
def _registry(registry):
    hook = _addHook(registry)
    yield
    _removeHook(hook)



class _Tube(object):
    """
    A L{_Tube} is an L{IDrain} and possibly also an L{IFount}, and provides
    lots of conveniences to make it easy to implement something that does fancy
    flow control with just a few methods.

    @ivar pump: the L{Pump} which will receive values from this tube and call
        C{deliver} to deliver output to it.  (When set, this will automatically
        set the C{tube} attribute of said L{Pump} as well, as well as
        un-setting the C{tube} attribute of the old pump.)

    @ivar _currentlyPaused: is this L{_Tube} currently paused?  Boolean: C{True}
        if paused, C{False} if not.

    @ivar _nextFount: XXX document me
    """
    _currentlyPaused = False
    _pumpReceiving = False
    _delivered = False
    _pump = None
    _nextFount = None

    def __init__(self, pump):
        """
        Initialize this L{_Tube} with the given L{Pump} to control its
        behavior.
        """
        self._pendingOutput = []
        self._tfount = _TubeFount(self)
        self._tdrain = _TubeDrain(self)
        self.pump = pump


    def _get_pump(self):
        """
        Getter for the C{pump} property.
        """
        return self._pump


    def _set_pump(self, newPump):
        """
        Setter for the C{pump} property.

        @param newPump: the new L{IPump}
        @type newPump: L{IPump}
        """
        if self._pump is not None:
            self._pump.tube = None
        self._pump = newPump
        self._pump.tube = self

    pump = property(_get_pump, _set_pump)


    def _unbufferSome(self):
        """
        Un-buffer some pending output into the downstream drain.
        """
        while self._pendingOutput and not self._currentlyPaused:
            item = self._pendingOutput.pop(0)
            self._tfount.drain.receive(item)


    def deliver(self, item):
        """
        Deliver the given item to this L{Tube}'s C{drain} attribute, if it has
        yet been set by L{flowingFrom}.
        """
        self._delivered = True
        drain = self._tfount.drain
        if drain is None:
            if not self._pendingOutput:
                self._tfount.pauseFlow()
            self._pendingOutput.append(item)
            return 1.0
        elif self._pumpReceiving:
            self._pendingOutput.append(item)
            return 0.5
        else:
            return drain.receive(item)


    _switchFlush = False

    def switch(self, drain):
        upstream = self._tdrain.fount
        upstream.pauseFlow()
        upstream.flowTo(drain)
        if self._pumpReceiving:
            self._switchFlush = True
        else:
            self._finishSwitching()


    def _finishSwitching(self):
        junk = self.pump.reassemble(self._pendingOutput)
        map(self._tdrain.fount.drain.receive, junk)


    @property
    def downstream(self):
        return self._tfount.drain



_pump_registry = AdapterRegistry()
_pump_registry.register([IPump], IDrain, '',
                        lambda pump: _pumpToTube(pump)._tdrain)
_pump_registry.register([IPump], IFount, '',
                        lambda pump: _pumpToTube(pump)._tfount)

from zope.interface.declarations import implementedBy

_pump_registry.register([implementedBy(_Tube)], IFount, '',
                        lambda tube: tube._tfount)
_pump_registry.register([implementedBy(_Tube)], IDrain, '',
                        lambda tube: tube._tdrain)
# _pump_registry = _registry(_pump_registry)


@implementer(IPump)
class Pump(object):
    """
    Null implementation for L{IPump}.  You can inherit from this to get no-op
    implementation of all of L{IPump}'s required implementation so you can just
    just implement the parts you're interested in.

    @ivar tube: The L{ITube} whose flow this pump is controlling.  This
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
