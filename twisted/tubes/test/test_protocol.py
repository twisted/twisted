# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.protocol}.
"""

from twisted.tubes.test.util import ResultProducingMixin
from twisted.tubes.test.util import StringEndpoint
from twisted.trial.unittest import TestCase
from twisted.tubes.protocol import factoryFromFlow
from twisted.tubes.tube import Pump
from twisted.tubes.tube import Tube
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



class FlowingAdapterTests(TestCase, ResultProducingMixin):
    """
    Tests for L{ProtocolAdapter}.
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

        self.tube = Tube(RememberingPump())


    def test_flowToSetsDrain(self):
        """
        L{ProtocolAdapter.flowTo} will set the C{drain} attribute of the
        L{ProtocolAdapter}.
        """
        self.adaptedFount.flowTo(self.tube)
        self.assertIdentical(self.adaptedFount.drain, self.tube)


    def test_flowToDeliversData(self):
        """
        L{ProtocolAdapter.flowTo} will cause subsequent calls to
        L{ProtocolAdapter.dataReceived} to invoke L{receive} on its drain.
        """
        self.adaptedFount.flowTo(self.tube)
        self.adaptedProtocol.dataReceived("some data")
        self.assertEquals(self.tube.pump.items, ["some data"])


    def test_stopFlowStopsConnection(self):
        """
        L{ProtocolAdapter.stopFlow} will close the underlying connection.
        """
        self.adaptedFount.flowTo(self.tube)
        self.adaptedFount.stopFlow()
        self.assertEquals(self.adaptedProtocol.transport.disconnecting, True)
        self.assertEquals(self.tube.pump.wasStopped, True)


    def test_flowingFromFlowControl(self):
        """
        L{ProtocolAdapter.flowingFrom} will establish the appropriate L{IFount}
        to deliver L{pauseFlow} notifications to.
        """
        ff = FakeFount()
        self.adaptedDrain.flowingFrom(ff)
        self.assertIdentical(self.adaptedDrain.fount, ff)



