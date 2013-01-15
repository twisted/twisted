# -*- test-case-name: twisted.tubes.test.test_protocol -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Objects to connect L{real data <twisted.internet.protocol.Protocol>} to
L{Tube}s.
"""

from zope.interface import implements
from twisted.tubes.itube import IDrain, IFount, ISegment
from twisted.internet.protocol import Protocol

class ProtocolDrain(object):
    implements(IDrain)

    fount = None
    inputType = ISegment

    def __init__(self, protocol):
        self._protocol = protocol


    # drain -> data being written from elsewhere
    def flowingFrom(self, fount):
        self.fount = fount
        # The transport is ready to receive data, so let's immediately indicate
        # that.


    def receive(self, item):
        self.transport.write(item)
        return 1.0


    def progress(self, amount=0.0):
        """
        This is a no-op since there's nothing to do to the underlying connection
        when progress occurs.
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
        self.transport.loseConnection()



class ProtocolFount(object):
    implements(IFount)

    drain = None
    outputType = ISegment

    def __init__(self, protocol):
        self._protocol = protocol


    # fount -> deliver data to elsewhere
    def flowTo(self, drain):
        """
        Flow to the given drain.
        """
        self.drain = drain
        self.drain.flowingFrom(self) # XXX test me
        return drain # XXX test me


    def switchFlowTo(self, newDrain, unprocessed=()):
        """
        Switch flow to the new drain.
        """
        self.drain = newDrain
        for chunk in unprocessed:
            self.drain.receive(chunk)


    _flowPaused = False
    def pauseFlow(self):
        """
        Pause flowing.
        """
        self._flowPaused = True
        self.transport.pauseProducing()


    def resumeFlow(self):
        """
        Resume flowing.
        """
        self._flowPaused = False
        self.transport.resumeProducing()


    def isFlowing(self):
        """
        Is this fount currently flowing?
        """
        return (
            self._flowStarted and not self._flowEnded and not self._flowPaused
        )


    def isEnded(self):
        """
        Is this fount completely done?  (Has it finished delivering all of its
        output to its C{drain}?)
        """
        return self._flowEnded


    _flowEnded = False
    def endFlow(self):
        """
        End the flow from this fount, dropping the TCP connection in the
        process.
        """
        # XXX really endFlow just ends the *read* connection.
        self._flowEnded = True
        self._protocol.transport.loseConnection()



class ProtocolPlumbing(Protocol, ProtocolDrain, ProtocolFount):
    """
    An adapter between an L{ITransport} and L{IFount} / L{IDrain} interfaces.

    The L{IFount} implementation represents the data being delievered from this
    transport; the bytes coming off the wire.

    The L{IDrain} implementation represents the data being sent I{to} this
    transport; being delivered to the peer.
    """

    # Private attributes for different components, so that we can pretend we're
    # composing instead of inheriting all this functionality.  This is a sort of
    # gross work around for the fact that proxyForInterface() doesn't support
    # multiple inheritance.  In order to be useful, the thing that the Deferred
    # from connect() fires with needs to provide both fount and drain.
    @property
    def _protocol(self):
        return self


    def __init__(self, createdStuff):
        # For sanity's sake, _protocol is set by __init__ above, but that code
        # is not currently actually used.  This has a 0-argument constructor and
        # the _protocol relay attribute instead to satisfy that dependency.
        self._createdStuff = createdStuff
        return


    @property
    def _drainImpl(self):
        return self


    @property
    def _fountImpl(self):
        return self

    # IProtocol -> deliver data to the drain, if any.

    def connectionMade(self):
        """
        The connection was established.  We don't want to deliver any data yet,
        maybe?
        """
        self._createdStuff(self, self)
        #self._drainImpl = ProtocolDrain(self)
        #self._fountImpl = ProtocolFount(self)


    def dataReceived(self, data):
        """
        Here's some data.  Data data data.

        Some data was received.
        """
        self._fountImpl.drain.receive(data)


    def connectionLost(self, reason):
        self._flowEnded = True



from twisted.internet.protocol import Factory

class ProtocolAdapterCreatorThing(Factory, object):
    """
    A L{ProtocolAdapterCreatorThing} produces objects which provide
    L{IProtocol} but also L{IDrain} and L{IFount}.
    """
    def __init__(self, createdStuff=lambda a, b: None):
        self.createdStuff = createdStuff


    def buildProtocol(self, addr):
        """
        Create that thing.
        """
        return ProtocolPlumbing(self.createdStuff)

