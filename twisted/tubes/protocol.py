# -*- test-case-name: twisted.tubes.test.test_protocol -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Objects to connect L{real data <twisted.internet.protocol.Protocol>} to
L{Tube}s.
"""

from zope.interface import implementer
from twisted.tubes.itube import IDrain, IFount, ISegment
from twisted.internet.protocol import Protocol as _Protocol
from twisted.internet.interfaces import IPushProducer


@implementer(IPushProducer)
class _FountProducer(object):
    def __init__(self, fount):
        self._fount = fount


    def pauseProducing(self):
        self._fount.pauseFlow()


    def resumeProducing(self):
        self._fount.resumeFlow()


    def stopProducing(self):
        self._fount.stopFlow()



@implementer(IDrain)
class _ProtocolDrain(object):

    fount = None
    inputType = ISegment

    def __init__(self, transport):
        self._transport = transport


    # drain -> data being written from elsewhere
    def flowingFrom(self, fount):
        self._transport.registerProducer(_FountProducer(fount), True)
        self.fount = fount
        # The transport is ready to receive data, so let's immediately indicate
        # that.


    def receive(self, item):
        self._transport.write(item)
        return 1.0


    def progress(self, amount=0.0):
        """
        This is a no-op since there's nothing to do to the underlying
        connection when progress occurs.
        """


    def flowStopped(self, reason):
        """
        The flow of data that should be written to the underlying transport has
        ceased.  Perform a half-close on the transport if possible so that it
        knows no further data is forthcoming.
        """
        # Hrm.  Not exactly sure what this would mean - we're not going to get
        # more data delievered to us... so... time to go away?  Actually, this
        # is ostensibly a half-close since the other end of the connection may
        # feel free to continue to deliver data to *us*...
        self._transport.loseConnection()



@implementer(IFount)
class _ProtocolFount(object):

    drain = None
    outputType = ISegment

    def __init__(self, transport):
        self._transport = transport


    # fount -> deliver data to elsewhere
    def flowTo(self, drain):
        """
        Flow to the given drain.
        """
        self.drain = drain
        self.drain.flowingFrom(self) # XXX test me
        return drain # XXX test me


    _flowPaused = False
    def pauseFlow(self):
        """
        Pause flowing.
        """
        self._flowPaused = True
        self._transport.pauseProducing()


    def resumeFlow(self):
        """
        Resume flowing.
        """
        self._flowPaused = False
        self._transport.resumeProducing()


    _flowEnded = False
    def stopFlow(self):
        """
        End the flow from this fount, dropping the TCP connection in the
        process.
        """
        # XXX really stopFlow just ends the *read* connection.
        self._flowEnded = True
        self._transport.loseConnection()



class _ProtocolPlumbing(_Protocol):
    """
    An adapter between an L{ITransport} and L{IFount} / L{IDrain} interfaces.

    The L{IFount} implementation represents the data being delievered from this
    transport; the bytes coming off the wire.

    The L{IDrain} implementation represents the data being sent I{to} this
    transport; being delivered to the peer.
    """

    # IProtocol -> deliver data to the drain, if any.

    def __init__(self, flow):
        self._flow = flow

    def connectionMade(self):
        """
        The connection was established.  We don't want to deliver any data yet,
        maybe?
        """
        self._drain = _ProtocolDrain(self.transport)
        self._fount = _ProtocolFount(self.transport)
        self._flow(self._fount, self._drain)


    def dataReceived(self, data):
        """
        Here's some data.  Data data data.

        Some data was received.
        """
        self._fount.drain.receive(data)


    def connectionLost(self, reason):
        self._flowEnded = True
        if self._fount.drain is not None:
            self._fount.drain.flowStopped(reason)
        # self._drain.fount.stopFlow()



from twisted.internet.protocol import Factory

class _FlowFactory(Factory):
    def __init__(self, flow):
        self.flow = flow


    def buildProtocol(self, addr):
        return _ProtocolPlumbing(self.flow)



def factoryFromFlow(flow):
    """
    Construct a L{Factory} that is great.

    @param flow: a 2-argument callable, taking (fount, drain).
    """
    return _FlowFactory(flow)

