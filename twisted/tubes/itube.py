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

        @raise AlreadyDraining: if there is already a drain (i.e.  C{flowTo} has
            already been called on this L{IFount}.)

        @return: another L{IFount} provider, or C{None}.  By convention, this
            will return the value of C{flowingFrom} and allow the drain to
            transform the C{outputType} (however, other transformations are
            allowed).
        """


    def switchFlowTo(newDrain, unprocessed=()):
        """
        Change the flow of this fount to point at a new drain.

        @param newDrain: a new L{IDrain}.

        @param unprocessed: an iterable of un-processed objects of this
            L{IFount}'s C{outputType} to pass on to the new thing.

        @return: same as C{IDrainFount.flowTo}
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


    def isFlowing():
        """
        Return a boolean: is this fount currently delivering output?  This means
        that it is started, it isn't paused, and it isn't ended (although it may
        be I{ending}).
        """


    def isEnded():
        """
        Return a boolean: has this fount finished delivering all output?
        """


    def endFlow():
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
            0.75 and 1.0. Note however that this value represents and
            I{estimate} and its exact semantics may vary considerably depending
            on the nature of the underlying transport.  In many cases, the
            amount of progress made is entirely unknown: for example, when some
            bytes are received by the underlying transport.  In those cases,
            C{None} should be passed here.
        @type amount: C{float} or C{NoneType}

        @return: C{None}
        """


    def flowStopped(reason):
        """
        The flow has stopped.  The given Failure object will say why.  After a
        L{IFount} invokes this method, it must stop invoking all other methods
        on this L{IDrain}.
        """



class IPump(Interface):
    """
    An L{IPump} provider is a control object for a L{Tube}.  A pump provides
    all the behavior associated with a the L{Tube}'s translation of input to
    output, so that users of L{Tube}'s buffering and pipeline establishment
    behavior don't need to inherit from anything in order to use it.  L{Pump}
    provides a default implementation which does nothing in response to every
    method.
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
        A reference to a L{Tube}.  This will be set externally.
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



class ISegment(Interface):
    """
    This is a marker interface for the arbitrarily-sized segments of data that
    a stream-oriented protocol may deliver.
    """


