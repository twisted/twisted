# -*- test-case-name: twisted.tubes.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utilities for testing L{twisted.tubes}.
"""

from zope.interface import Interface, implements, implementer
from zope.interface.verify import verifyClass

from twisted.test.proto_helpers import StringTransport
from twisted.internet.defer import succeed
from twisted.tubes.itube import IDrain
from twisted.tubes.itube import IFount
from twisted.tubes.itube import ISwitchablePump
from twisted.tubes.tube import Pump


class StringEndpoint(object):
    """
    An endpoint which connects to a L{StringTransport}
    """
    def __init__(self):
        """
        Initialize the list of connected transports.
        """
        self.transports = []


    def connect(self, factory):
        """
        Connect the given L{IProtocolFactory} to a L{StringTransport} and
        return a fired L{Deferred}.
        """
        protocol = factory.buildProtocol(None)
        transport = StringTransport()
        transport.protocol = protocol
        protocol.makeConnection(transport)
        return succeed(protocol)



class IFakeOutput(Interface):
    ""



class IFakeInput(Interface):
    ""



class FakeDrain(object):
    """
    Implements a fake IDrain for testing.
    """

    implements(IDrain)

    inputType = IFakeInput

    fount = None
    stopped = None

    def __init__(self):
        self.received = []
        self.stopped = []
        self.progressed = []


    def flowingFrom(self, fount):
        self.fount = fount


    def receive(self, item):
        self.received.append(item)


    def flowStopped(self, reason):
        self.stopped.append(reason)


    def progress(self, amount=None):
        self.progressed.append(amount)

verifyClass(IDrain, FakeDrain)



class FakeFount(object):
    """
    Fake fount implementation for testing.
    """
    implements(IFount)

    outputType = IFakeOutput

    flowIsPaused = False
    flowIsStopped = False

    def flowTo(self, drain):
        self.drain = drain
        return self.drain.flowingFrom(self)


    def pauseFlow(self):
        if self.flowIsPaused:
            raise Exception("The flow is paused.")
        self.flowIsPaused = True


    def resumeFlow(self):
        if not self.flowIsPaused:
            raise Exception("The flow was not paused yet.")
        self.flowIsPaused = False


    def stopFlow(self):
        self.flowIsStopped = True

verifyClass(IFount, FakeFount)



class TesterPump(Pump):
    """
    Pump for testing that records its inputs.
    """

    def __init__(self):
        """
        Initialize structures for recording.
        """
        self.allReceivedItems = []


    def received(self, item):
        """
        Recieved an item, remember it.
        """
        self.allReceivedItems.append(item)



@implementer(ISwitchablePump)
class SwitchableTesterPump(TesterPump):
    """
    A L{TesterPump} that supports reassembly.
    """

    def reassemble(self, data):
        """
        Do nothing.
        """
        return []
