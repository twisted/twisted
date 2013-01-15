# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.tube}.
"""

from twisted.trial.unittest import TestCase
from twisted.tubes.test.util import TesterValve
from twisted.tubes.test.util import FakeFount
from twisted.tubes.test.util import FakeDrain
from twisted.tubes.tube import Valve
from twisted.tubes.tube import Tube
from twisted.tubes.test.util import IFakeInput

class TubeTest(TestCase):
    """
    Tests for L{Tube}.
    """

    def setUp(self):
        """
        Create a tube, and a fake drain and fount connected to it.
        """
        self.tube = Tube(TesterValve())
        self.ff = FakeFount()
        self.fd = FakeDrain()


    def test_valveAttribute(self):
        """
        The L{Tube.valve} conveniently keeps L{Valve.tube} up to date when you
        set it.
        """
        firstValve = self.tube.valve
        secondValve = Valve()
        self.assertIdentical(firstValve.tube, self.tube)
        self.assertIdentical(secondValve.tube, None)
        self.tube.valve = secondValve
        self.assertIdentical(firstValve.tube, None)
        self.assertIdentical(secondValve.tube, self.tube)


    def test_flowingFromFirst(self):
        """
        If L{Tube.flowingFrom} is called before L{Tube.flowTo}, the argument to
        L{Tube.flowTo} will immediately have its L{IDrain.flowingFrom} called.
        """
        self.ff.flowTo(self.tube)
        self.tube.flowTo(self.fd)
        self.assertIdentical(self.fd.fount, self.tube)


    def test_tubeReceiveCallsValveReceived(self):
        """
        L{Tube.receive} will call C{valve}.
        """
        got = []
        class V(Valve):
            def received(self, item):
                got.append(item)
        self.tube.valve = V()
        result = self.tube.receive("sample item")
        self.assertEqual(result, 0.5)
        self.assertEqual(got, ["sample item"])


    def test_tubeReceiveRelaysValveReceivedResult(self):
        """
        L{Tube.receive} will call C{Valve.received}.
        """
        got = []
        class V(Valve):
            def received(self, item):
                got.append(item)
                return 0.8
        self.tube.valve = V()
        result = self.tube.receive("some input")
        self.assertEqual(result, 0.8)
        self.assertEqual(got, ["some input"])


    def test_tubeProgressRelaysValveProgress(self):
        """
        L{Tube.progress} will call L{Valve.progress}, and also call
        L{IDrain.progress}.
        """
        got = []
        class V(Valve):
            def progressed(self, amount=None):
                got.append(amount)
        self.tube.valve = V()
        self.assertEqual(got, [])
        self.tube.progress()
        self.tube.progress(0.6)
        self.assertEqual(got, [None, 0.6])


    def test_tubeReceiveRelaysProgressDownStream(self):
        """
        L{Tube.receive} will call its downstream L{IDrain}'s C{progress} method
        if its L{Valve} does not call its C{deliver} method.
        """
        got = []
        class V(Valve):
            def progressed(self, amount=None):
                got.append(amount)
        self.tube.flowTo(Tube(V()))
        self.tube.receive(2)
        self.assertEquals(got, [None])


    def test_tubeReceiveDoesntRelayUnnecessaryProgress(self):
        """
        L{Tube.receive} will not call its downstream L{IDrain}'s C{progress}
        method if its L{Valve} I{does} call its C{deliver} method.
        """
        got = []
        class V(Valve):
            def received(self, item):
                self.tube.deliver(item + 1)
        class V1(Valve):
            def progressed(self, amount=None):
                got.append(amount)
        self.tube.__init__(V())
        self.tube.flowTo(Tube(V1()))
        self.tube.receive(2)
        self.assertEquals(got, [])


    def test_flowToFirst(self):
        """
        If L{Tube.flowTo} is called before L{Tube.flowingFrom}, the argument to
        L{Tube.flowTo} will have its L{flowingFrom} called when
        L{Tube.flowingFrom} is called.
        """
        self.tube.flowTo(self.fd)
        self.ff.flowTo(self.tube)
        self.assertIdentical(self.fd.fount, self.tube)


    def test_flowFromTypeCheck(self):
        """
        L{Tube.flowingFrom} checks the type of its input.  If it doesn't match
        (both are specified explicitly, and they don't match).
        """
        class V(Valve):
            inputType = IFakeInput
        self.tube.valve = V()
        self.failUnlessRaises(TypeError, self.ff.flowTo, self.tube)


    def test_flowToValue(self):
        """
        L{Tube.flowTo} returns the L{Tube} being flowed to.
        """
        tubeB = Tube(Valve())
        result = self.tube.flowTo(tubeB)
        self.assertIdentical(result, tubeB)


    def test_deliverPostsDownstream(self):
        """
        L{Tube.deliver} on a connected tube will call '.receive()' on its drain.
        """
        self.ff.flowTo(self.tube).flowTo(self.fd)
        self.tube.deliver(7)
        self.assertEquals(self.fd.received, [7])


    def test_deliverWaitsUntilThereIsADownstream(self):
        """
        L{Tube.deliver} on a disconnected tube will buffer its input until
        there's an active drain to deliver to.
        """
        self.tube.deliver("hi")
        self.tube.flowTo(self.fd)
        self.assertEquals(self.fd.received, ["hi"])


    def test_deliverWithoutDownstreamPauses(self):
        """
        L{Tube.deliver} on a tube with an upstream L{IFount} but no downstream
        L{IDrain} will pause its L{IFount}.  This is because the L{Tube} has to
        buffer everything downstream, and it doesn't want to buffer infinitely;
        if it has nowhere to deliver onward to, then it issues a pause.  Note
        also that this happens when data is delivered via the L{Tube} and
        I{not} when data arrives via the L{Tube}'s C{receive} method, since
        C{receive} delivers onwards to the L{Valve} immediately, and does not
        require any buffering.
        """
        self.ff.flowTo(self.tube)
        self.tube.deliver("abc")
        self.assertEquals(self.ff.flowIsPaused, True)


    def test_receiveCallsValveReceived(self):
        """
        L{Tube.receive} will deliver its input to L{IValve.received} on its
        valve.
        """
        self.tube.receive("one-item")
        self.assertEquals(self.tube.valve.allReceivedItems,
                          ["one-item"])



