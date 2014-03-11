# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.protocol}.
"""

from twisted.tubes.test.util import StringEndpoint
from twisted.trial.unittest import TestCase
from twisted.tubes.protocol import factoryFromFlow
from twisted.tubes.tube import Pump
from twisted.tubes.tube import series
from twisted.python.failure import Failure
from twisted.tubes.test.util import FakeDrain
from twisted.tubes.test.util import FakeFount

class RememberingPump(Pump):
    """
    A pump that remembers what it receives.

    @ivar items: a list of objects that have been received.
    """

    def __init__(self):
        self.items = []
        self.wasStopped = False
        self.started()


    def received(self, item):
        self.items.append(item)


    def stopped(self, reason):
        self.wasStopped = True
        self.reason = reason



class FlowingAdapterTests(TestCase):
    """
    Tests for L{factoryFromFlow} and the drain/fount/factory adapters it
    constructs.
    """

    def setUp(self):
        """
        Sert up these tests.
        """
        self.endpoint = StringEndpoint()
        def flowFunction(fount, drain):
            self.adaptedDrain = drain
            self.adaptedFount = fount
        self.adaptedProtocol = self.successResultOf(
            self.endpoint.connect(factoryFromFlow(flowFunction))
        )

        self.pump = RememberingPump()
        self.tube = series(self.pump)


    def test_progressNoOp(self):
        """
        L{_ProtocolDrain.progress} does nothing, but has the correct signature.

        @see: L{twisted.tubes.test.test_tube.PumpTest.test_noOps}
        """
        self.adaptedDrain.progress()
        self.adaptedDrain.progress(0.5)


    def test_flowToSetsDrain(self):
        """
        L{_ProtocolFount.flowTo} will set the C{drain} attribute of the
        L{_ProtocolFount}.
        """
        self.adaptedFount.flowTo(self.tube)
        self.assertIdentical(self.adaptedFount.drain, self.tube)


    def test_flowToDeliversData(self):
        """
        L{_ProtocolFount.flowTo} will cause subsequent calls to
        L{_ProtocolFount.dataReceived} to invoke L{receive} on its drain.
        """
        self.adaptedFount.flowTo(self.tube)
        self.adaptedProtocol.dataReceived("some data")
        self.assertEqual(self.pump.items, ["some data"])


    def test_drainReceivingWritesToTransport(self):
        """
        Calling L{receive} on a L{_ProtocolDrain} will send the data to the
        wrapped transport.
        """
        HELLO = b"hello world!"
        self.adaptedDrain.receive(HELLO)
        self.assertEqual(self.endpoint.transports[0].io.getvalue(), HELLO)


    def test_stopFlowStopsConnection(self):
        """
        L{_ProtocolFount.stopFlow} will close the underlying connection by
        calling C{loseConnection} on it.
        """
        self.adaptedFount.flowTo(self.tube)
        self.adaptedFount.stopFlow()
        self.assertEqual(self.adaptedProtocol.transport.disconnecting, True)
        # The connection has not been closed yet; we *asked* the flow to stop,
        # but it may not have done.
        self.assertEqual(self.pump.wasStopped, False)


    def test_flowStoppedStopsConnection(self):
        """
        L{_ProtocolDrain.flowStopped} will close the underlying connection by
        calling C{loseConnection} on it.
        """
        self.adaptedFount.flowTo(self.tube)
        self.adaptedDrain.flowStopped(Failure(ZeroDivisionError()))
        self.assertEqual(self.adaptedProtocol.transport.disconnecting, True)
        self.assertEqual(self.pump.wasStopped, False)


    def test_connectionLostSendsFlowStopped(self):
        """
        When C{connectionLost} is called on a L{_ProtocolPlumbing} and it has
        an L{IFount} flowing to it (in other words, flowing to its
        L{_ProtocolDrain}), but no drain flowing I{from} it, the L{IFount}
        should have C{stopFlow} invoked on it so that it will no longer deliver
        to the now-dead transport.
        """
        self.adaptedFount.flowTo(self.tube)
        class MyFunException(Exception):
            "An exception."
        f = Failure(MyFunException())
        self.adaptedProtocol.connectionLost(f)
        self.assertEqual(self.pump.wasStopped, True)
        self.assertIdentical(f, self.pump.reason)


    def test_connectionLostSendsStopFlow(self):
        """
        L{_ProtocolPlumbing.connectionLost} will notify its C{_drain}'s
        C{fount} that it should stop flowing, since the connection is now gone.
        """
        ff = FakeFount()
        ff.flowTo(self.adaptedDrain)
        self.assertEqual(ff.flowIsStopped, False)
        self.adaptedProtocol.connectionLost(Failure(ZeroDivisionError))
        self.assertEqual(ff.flowIsStopped, True)


    def test_dataReceivedBeforeFlowing(self):
        """
        If L{_ProtocolPlumbing.dataReceived} is called before its
        L{_ProtocolFount} is flowing to anything, then it will pause the
        transport but only until the L{_ProtocolFount} is flowing to something.
        """
        self.adaptedProtocol.dataReceived("hello, ")
        self.assertEqual(self.adaptedProtocol.transport.producerState,
                          'paused')
        # It would be invalid to call dataReceived again in this state, so no
        # need to test that...
        fd = FakeDrain()
        self.adaptedFount.flowTo(fd)
        self.assertEqual(self.adaptedProtocol.transport.producerState,
                         'producing')
        self.adaptedProtocol.dataReceived("world!")
        self.assertEqual(fd.received, ["hello, ", "world!"])


    def test_dataReceivedBeforeFlowingThenFlowTo(self):
        """
        Repeated calls to L{flowTo} don't replay the buffer from
        L{dataReceived} to the new drain.
        """
        self.test_dataReceivedBeforeFlowing()
        fd2 = FakeDrain()
        self.adaptedFount.flowTo(fd2)
        self.adaptedProtocol.dataReceived("hooray")
        self.assertEqual(fd2.received, ["hooray"])


    def test_dataReceivedWhenFlowingToNone(self):
        """
        Initially flowing to L{None} is the same as flowTo never having been
        called, so L{_ProtocolFount.dataReceived} should have the same effect.
        """
        self.adaptedFount.flowTo(None)
        self.test_dataReceivedBeforeFlowing()


    def test_flowingToNoneAfterFlowingToSomething(self):
        """
        Flowing to L{None} should disconnect from any drain, no longer
        delivering it output.
        """
        fd = FakeDrain()
        self.adaptedFount.flowTo(fd)
        self.adaptedProtocol.dataReceived("a")
        self.adaptedFount.flowTo(None)
        self.assertEqual(fd.fount, None)
        self.test_dataReceivedBeforeFlowing()
        self.assertEqual(fd.received, ["a"])


    def test_flowingFromAttribute(self):
        """
        L{ProtocolAdapter.flowingFrom} will establish the appropriate L{IFount}
        to deliver L{pauseFlow} notifications to.
        """
        ff = FakeFount()
        self.adaptedDrain.flowingFrom(ff)
        self.assertIdentical(self.adaptedDrain.fount, ff)


    def test_pauseUnpauseFromTransport(self):
        """
        When an L{IFount} produces too much data for a L{_ProtocolDrain} to
        process, the L{push producer
        <twisted.internet.interfaces.IPushProducer>} associated with the
        L{_ProtocolDrain}'s transport will relay the L{pauseProducing}
        notification to that L{IFount}'s C{pauseFlow} method.
        """
        ff = FakeFount()
        # Sanity check.
        self.assertEqual(ff.flowIsPaused, False)
        self.adaptedDrain.flowingFrom(ff)
        # The connection is too full!  Back off!
        self.adaptedProtocol.transport.producer.pauseProducing()
        self.assertEqual(ff.flowIsPaused, True)
        # All clear, start writing again.
        self.adaptedProtocol.transport.producer.resumeProducing()
        self.assertEqual(ff.flowIsPaused, False)


    def test_pauseUnpauseFromOtherDrain(self):
        """
        When a L{_ProtocolFount} produces too much data for a L{drain <IDrain>}
        to process, and it calls L{_ProtocolFount.pauseFlow}, the underlying
        transport will be paused.
        """
        fd = FakeDrain()
        # StringTransport is an OK API.  But it is not the _best_ API.
        PRODUCING = 'producing'
        PAUSED = 'paused'
        # Sanity check.
        self.assertEqual(self.adaptedProtocol.transport.producerState,
                         PRODUCING)
        self.adaptedFount.flowTo(fd)
        # Steady as she goes.
        self.assertEqual(self.adaptedProtocol.transport.producerState,
                         PRODUCING)
        anPause = fd.fount.pauseFlow()
        self.assertEqual(self.adaptedProtocol.transport.producerState,
                         PAUSED)
        anPause.unpause()
        self.assertEqual(self.adaptedProtocol.transport.producerState,
                         PRODUCING)


    def test_stopProducing(self):
        """
        When C{stopProducing} is called on the L{push producer
        <twisted.internet.interfaces.IPushProducer>} associated with the
        L{_ProtocolDrain}'s transport, the L{_ProtocolDrain}'s C{fount}'s
        C{stopFlow} method will be invoked.
        """
        ff = FakeFount()
        ff.flowTo(self.adaptedDrain)
        self.adaptedDrain._transport.producer.stopProducing()
        self.assertEqual(ff.flowIsStopped, True)


    def test_flowingFrom(self):
        """
        L{_ProtocolFount.flowTo} returns the result of its argument's
        C{flowingFrom}.
        """
        another = FakeFount()
        class ReflowingFakeDrain(FakeDrain):
            def flowingFrom(self, fount):
                super(ReflowingFakeDrain, self).flowingFrom(fount)
                return another
        anotherOther = self.adaptedFount.flowTo(ReflowingFakeDrain())
        self.assertIdentical(another, anotherOther)
