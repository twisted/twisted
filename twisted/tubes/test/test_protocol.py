# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.protocol}.
"""

from twisted.tubes.test.util import ResultProducingMixin
from twisted.tubes.test.util import StringEndpoint
from twisted.trial.unittest import TestCase
from twisted.tubes.protocol import ProtocolAdapterCreatorThing
from twisted.tubes.tube import Pump
from twisted.tubes.tube import Tube
from twisted.tubes.test.util import FakeFount

class FlowingAdapterTests(TestCase, ResultProducingMixin):
    """
    Tests for L{ProtocolAdapter}.
    """

    def setUp(self):
        """
        Sert up these tests.
        """
        self.endpoint = StringEndpoint()
        self.adapter = self.result(
            self.endpoint.connect(ProtocolAdapterCreatorThing())).now()
        class TestPump(Pump):
            def __init__(self):
                self.items = []

            def received(self, item):
                self.items.append(item)

        self.tube = Tube(TestPump())


    def test_flowToSetsDrain(self):
        """
        L{ProtocolAdapter.flowTo} will set the C{drain} attribute of the
        L{ProtocolAdapter}.
        """
        self.adapter.flowTo(self.tube)
        self.assertIdentical(self.adapter.drain, self.tube)


    def test_flowToDeliversData(self):
        """
        L{ProtocolAdapter.flowTo} will cause subsequent calls to
        L{ProtocolAdapter.dataReceived} to invoke L{receive} on its drain.
        """
        self.adapter.flowTo(self.tube)
        self.adapter.dataReceived("some data")
        self.assertEquals(self.tube.pump.items, ["some data"])


    def test_endFlowStopsConnection(self):
        """
        L{ProtocolAdapter.endFlow} will close the underlying connection.
        """
        self.adapter.flowTo(self.tube)
        self.adapter.endFlow()
        self.assertEquals(self.adapter.transport.disconnecting, True)
        self.assertEqual(self.adapter.isEnded(), True)


    def test_flowingFromFlowControl(self):
        """
        L{ProtocolAdapter.flowingFrom} will establish the appropriate L{IFount}
        to deliver L{pauseFlow} notifications to.
        """
        ff = FakeFount()
        self.adapter.flowingFrom(ff)
        self.assertIdentical(self.adapter.fount, ff)



