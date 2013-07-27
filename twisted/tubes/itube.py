# -*- test-case-name: twisted.tubes.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interfaces related to data flows.
"""

from zope.interface import Interface, Attribute

class IFount(Interface):
    """
    A fount produces objects for a drain to consume.
    """

    outputType = Attribute(
        """
        The type of output produced by this Fount.

        This may be an L{IInterface} provider.
        """)

    drain = Attribute(
        """
        The L{IDrain} currently accepting input from this L{IFount}.
        (Read-only; should raise L{AttributeError} if set.)
        """)


    def flowTo(drain):
        """
        Add a drain to this fount to consume its output.

        This will I{synchronously} call L{flowingFrom(fount)
        <IDrain.flowingFrom>} on C{drain} to indicate to C{drain} which
        L{IFount} its future input will come from - I{unless} this L{IFount} is
        exhausted and will never produce more output.  In this case, C{flowTo}
        must I{not} call C{flowingFrom}, and must return L{None}.

        Typically, this will return the result of L{drain.flowingFrom(fount)
        <IDrain.flowingFrom>} to allow construction of pipelines with the
        C{x.flowTo(...).flowTo(...).flowTo(...)} idiom; however,
        implementations of L{IFount} are at liberty to return L{None} or any
        valid L{IFount}.

        @raise AlreadyDraining: if there is already a drain (i.e.  C{flowTo}
            has already been called on this L{IFount}.)

        @return: another L{IFount} provider, or C{None}.  By convention, this
            will return the value of C{flowingFrom} and allow the drain to
            transform the C{outputType} (however, other transformations are
            allowed).
        """


    def pauseFlow():
        """
        Momentarily pause delivering items to the currently active drain, until
        C{resumeFlow} is called.
        """


    def resumeFlow():
        """
        Resume delivering items to the drain.
        """


    def stopFlow():
        """
        End the flow from this L{IFount}; it should never call L{IDrain.receive}
        again.
        """



class IDrain(Interface):
    """
    A drain consumes objects from a fount.
    """

    inputType = Attribute(
        """
        Similar to L{IFount.outputType}.
        """)

    fount = Attribute(
        """
        The fount that is delivering data to this L{IDrain}.
        """)


    def flowingFrom(fount):
        """
        This drain is now accepting a flow from the given L{IFount}.

        @return: another L{IFount}, if this L{IDrain} will produce more data,
            or C{None}.
        """


    def receive(item):
        """
        An item was received from the fount.

        @param item: an instance of L{IDrain.receiveType}

        @return: a floating point number between 0.0 and 1.0, indicating the how
            full any buffers on the way to processing the data are (0-100%).
            Note that this may be greater than 100%, in which case you should
            probably stop sending for a while and give it a chance to recover.
        """


    def progress(amount=None):
        """
        An item was received at some lower level interface; progress is being
        made towards the next item that will be passed to 'receive'.

        This method can be implemented in order to facilitate timeout logic.
        For example, if you have a file downloader that might be used to
        download a multi-gigabyte file and then deliver that file's name to an
        L{IDrain}, that L{IDrain} will be waiting a long time to receive that
        one item to C{receive()}.  However, timeout logic usually belongs with
        the ultimate consumer of an API, which in this case would be the
        very-infrequently-called L{IDrain}.  So, that L{IDrain} could implement
        C{progress} to re-set a short timeout, so that it can shut down an idle
        connection that is receiving nothing, but it won't shut down a
        connection that is functioning perfectly well but slightly slower than
        expected.

        @param amount: An optional floating-point number between 0.0 and 1.0
            indicating the estimated amount of progress made towards the next
            call to L{receive} on this L{IDrain}.  For example, if an item is
            received in 4 chunks, this would ideally be called with 0.25, 0.5,
            0.75 and 1.0. Note however that this value represents an
            I{estimate} and its exact semantics may vary considerably depending
            on the nature of the underlying transport.  In fact, although
            callers really should remain within the 0.0/1.0 range,
            implementations of this method should be resilient to invalid
            values, and treat any value outside that range as equivalent to
            C{None}.  In many cases, the amount of progress made is entirely
            unknown: for example, when some bytes are received by the
            underlying transport when no length prefix is avialable in the
            transport protocol.  In those cases, C{None} should be passed here.
        @type amount: C{float} or C{NoneType}

        @return: C{None}
        """


    def flowStopped(reason):
        """
        The flow has stopped.  The given L{Failure
        <twisted.internet.failure.Failure>} object indicates why.  After a
        L{IFount} invokes this method, it must stop invoking all other methods
        on this L{IDrain}.

        @param reason: The reason why the flow has terminated.  This may be any
            exception type, depending on the L{IFount} delivering data to this
            L{IDrain}.
        @type reason: L{Failure <twisted.internet.failure.Failure>}
        """



class IPump(Interface):
    """
    An L{IPump} provider is a control object for an L{ITube}.  A pump provides
    all the behavior associated with the L{ITube}'s translation of input to
    output, so that users of the L{ITube}'s buffering and pipeline
    establishment behavior don't need to inherit from anything in order to use
    it.  L{Pump} provides a default implementation which does nothing in
    response to every method.

    Look at this awesome ASCII art::

                         a fount
                      +----+--------+               +-----  a
                     / +---+------+ | | data flow  / +----  fount
                    / /           | | v           / /
                   /o+---O a pump | |            /o+---O a pump
                  / /             | |  a drain  / /
        a     ---+ /              | +----+-----+ /
        drain ----+               +------+------+

              =========> direction of flow =========>

    (Image credit Nam Nguyen)
    """

    inputType = Attribute(
        """
        The type expected to be received as input to received.
        """
    )

    outputType = Attribute(
        """
        The type expected to be sent as output to C{tube.deliver}.
        """
    )

    tube = Attribute(
        """
        A reference to an L{ITube}.  This will be set externally.
        """)


    def started():
        """
        The flow of items has started.  C{received} may be called at any point
        after this.
        """


    def received(item):
        """
        An item was received from 'upstream', i.e. the framework, or the
        lower-level data source that this L{Pump} is interacting with.
        """


    def progressed(amount=None):
        """
        Some progress was made.
        """


    def stopped(reason):
        """
        The flow of data was stopped.
        """



class ISwitchablePump(IPump):
    """
    An L{ISwitchablePump} is an extension on top of L{IPump} which provides
    support for L{ISwitchableTube.switch} through L{reassemble}.
    """

    tube = Attribute(
        """
        A reference to an L{ISwitchableTube}.  This will be set externally.
        """)


    def reassemble(data):
        """
        Reverse the transformation done between the L{ISwitchableTube} calling
        L{received} and the L{ISwitchablePump} calling C{tube.deliver}.

        L{reassemble} will be called from L{ISwitchableTube.switch}, and the
        new L{IDrain} passed to C{switch} will have its C{receive} method
        called with each object of the reassembled data.

        @param data: The objects which had been passed to C{tube.deliver} which
            had been buffered by the L{ISwitchableTube}.

        @type data: L{list}

        @returns: A list of objects such that, if L{received} was called
            successively with each object in the returned list, C{tube.deliver}
            would be called successively with each object in C{data}. This does
            not need to be exactly equal to what was originally passed in as
            long as it achieves the same effect. Any objects which were
            buffered by the L{ISwitchablePump} which did not yet correspond to
            a C{tube.deliver} call should be included as well.

        @rtype: L{list}
        """



class ITube(Interface):
    """
    An L{ITube} is an L{IDrain} and possibly also an L{IFount}, and provides
    lots of conveniences to make it easy to implement something that does fancy
    flow control with just a few methods.
    """

    pump = Attribute(
        """
        The L{Pump} which will receive values from this tube and call
        C{deliver} to deliver output to it. (When set, this will automatically
        set the C{tube} attribute of said L{Pump} as well, as well as
        un-setting the C{tube} attribute of the old pump.)
        """
    )


    def deliver(item):
        """
        Deliver the given item to this L{ITube}'s L{IDrain}, if something is
        flowing from the L{IDrain}.
        """


class ISwitchableTube(ITube):
    """
    L{ISwitchableTube} is an extension on top of L{ITube} which also allows the
    tube's underlying L{IDrain} to be swapped for another L{IDrain} with the
    L{switch} method.
    """

    pump = Attribute(
        """
        Similar to L{ITube.pump}, except an object implementing the
        L{ISwitchablePump} interface.
        """
    )


    def switch(drain):
        """
        Start pumping to another drain.

        Any data buffered by the L{ISwitchableTube} will be reassembled using
        C{pump.reassemble} (i.e. L{SwitchablePump.reassemble}) and then passed
        to the new L{IDrain}'s C{receive} method.
        """



class ISegment(Interface):
    """
    This is a marker interface for the arbitrarily-sized segments of data that
    a stream-oriented protocol may deliver.
    """
