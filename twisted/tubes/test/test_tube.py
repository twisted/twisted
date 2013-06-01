# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.tube}.
"""

from twisted.trial.unittest import TestCase
from twisted.tubes.test.util import TesterPump, FakeFount, FakeDrain, IFakeInput
from twisted.tubes.tube import Pump, cascade

class TubeTest(TestCase):
    """
    Tests for L{cascade}.
    """

    def setUp(self):
        """
        Create a tube, and a fake drain and fount connected to it.
        """
        self.pump = TesterPump()
        self.tubeDrain = cascade(self.pump)
        self.tube = self.pump.tube
        self.ff = FakeFount()
        self.fd = FakeDrain()


    def test_pumpAttribute(self):
        """
        The L{_Tube.pump} conveniently keeps L{Pump.tube} up to date when you
        set it.
        """
        firstPump = self.pump
        secondPump = Pump()
        self.assertIdentical(firstPump.tube, self.tube)
        self.assertIdentical(secondPump.tube, None)
        self.tube.pump = secondPump
        self.assertIdentical(firstPump.tube, None)
        self.assertIdentical(secondPump.tube, self.tube)


    def test_pumpStarted(self):
        """
        The L{_Tube} starts its L{Pump} upon C{flowingFrom}.
        """
        class Starter(Pump):
            def started(self):
                self.tube.deliver("greeting")

        self.ff.flowTo(cascade(Starter(), self.fd))
        self.assertEquals(self.fd.received, ["greeting"])


    def test_pumpFlowSwitching(self):
        """

        """


    def test_flowingFromFirst(self):
        """
        If L{_Tube.flowingFrom} is called before L{_Tube.flowTo}, the argument
        to L{_Tube.flowTo} will immediately have its L{IDrain.flowingFrom}
        called.
        """
        self.ff.flowTo(self.tubeDrain).flowTo(self.fd)
        self.assertNotIdentical(self.fd.fount, None)


    def test_tubeReceiveCallsPumpReceived(self):
        """
        L{_Tube.receive} will call C{pump.received} and synthesize a fake "0.5"
        progress result if L{None} is returned.
        """
        got = []
        class ReceivingPump(Pump):
            def received(self, item):
                got.append(item)
        self.tube.pump = ReceivingPump()
        result = self.tubeDrain.receive("sample item")
        self.assertEqual(result, 0.5)
        self.assertEqual(got, ["sample item"])


    def test_tubeReceiveRelaysPumpReceivedResult(self):
        """
        L{_Tube.receive} will call C{Pump.received} and relay its resulting
        progress value if one is provided.
        """
        got = []
        class ReceivingPumpWithProgress(Pump):
            def received(self, item):
                got.append(item)
                return 0.8
        self.tube.pump = ReceivingPumpWithProgress()
        result = self.tubeDrain.receive("some input")
        self.assertEqual(result, 0.8)
        self.assertEqual(got, ["some input"])


    def test_tubeProgressRelaysPumpProgress(self):
        """
        L{_Tube.progress} will call L{Pump.progress}, and also call
        L{IDrain.progress}.
        """
        got = []
        class ProgressingPump(Pump):
            def progressed(self, amount=None):
                got.append(amount)
        self.tube.pump = ProgressingPump()
        self.assertEqual(got, [])
        self.tubeDrain.progress()
        self.tubeDrain.progress(0.6)
        self.assertEqual(got, [None, 0.6])


    def test_tubeReceiveRelaysProgressDownStream(self):
        """
        L{_TubeDrain.receive} will call its downstream L{IDrain}'s C{progress}
        method if its L{Pump} does not call its C{deliver} method.
        """
        got = []
        class ProgressingPump(Pump):
            def progressed(self, amount=None):
                got.append(amount)
        self.ff.flowTo(self.tubeDrain).flowTo(cascade(ProgressingPump()))
        self.tubeDrain.receive(2)
        self.assertEquals(got, [None])


    def test_tubeReceiveDoesntRelayUnnecessaryProgress(self):
        """
        L{_Tube.receive} will not call its downstream L{IDrain}'s C{progress}
        method if its L{Pump} I{does} call its C{deliver} method.
        """
        got = []
        class ReceivingPump(Pump):
            def received(self, item):
                return [item + 1]
        class ProgressingPump(Pump):
            def progressed(self, amount=None):
                got.append(amount)
        self.tube.pump = ReceivingPump()
        self.ff.flowTo(self.tubeDrain).flowTo(cascade(ProgressingPump()))
        self.tubeDrain.receive(2)
        self.assertEquals(got, [])

    test_tubeReceiveDoesntRelayUnnecessaryProgress.todo = "The problem here is that 'tube' isn't a tube any more."


    def test_flowToFirst(self):
        """
        If L{_Tube.flowTo} is called before L{_Tube.flowingFrom}, the argument to
        L{_Tube.flowTo} will have its L{flowingFrom} called when
        L{_Tube.flowingFrom} is called.
        """
        cascade(self.tube, self.fd)
        self.ff.flowTo(self.tubeDrain)
        self.ff.drain.receive(3)
        self.tube.deliver(self.pump.allReceivedItems.pop())
        self.assertEquals(self.fd.received, [3])
        # self.assertIdentical(self.fd.fount, self.tube)


    def test_flowFromTypeCheck(self):
        """
        L{_Tube.flowingFrom} checks the type of its input.  If it doesn't match
        (both are specified explicitly, and they don't match).
        """
        class ToPump(Pump):
            inputType = IFakeInput
        self.tube.pump = ToPump()
        self.failUnlessRaises(TypeError, self.ff.flowTo, self.tubeDrain)


    def test_deliverPostsDownstream(self):
        """
        L{_Tube.deliver} on a connected tube will call '.receive()' on its drain.
        """
        self.ff.flowTo(self.tubeDrain).flowTo(self.fd)
        self.tube.deliver(7)
        self.assertEquals(self.fd.received, [7])


    def test_deliverWaitsUntilThereIsADownstream(self):
        """
        L{_Tube.deliver} on a disconnected tube will buffer its input until
        there's an active drain to deliver to.
        """
        self.tube.deliver("hi")
        nextFount = self.ff.flowTo(self.tubeDrain)
        nextFount.flowTo(self.fd)
        self.assertEquals(self.fd.received, ["hi"])


    def test_deliverWithoutDownstreamPauses(self):
        """
        L{_Tube.deliver} on a tube with an upstream L{IFount} but no downstream
        L{IDrain} will pause its L{IFount}.  This is because the L{_Tube} has to
        buffer everything downstream, and it doesn't want to buffer infinitely;
        if it has nowhere to deliver onward to, then it issues a pause.  Note
        also that this happens when data is delivered via the L{_Tube} and
        I{not} when data arrives via the L{_Tube}'s C{receive} method, since
        C{receive} delivers onwards to the L{Pump} immediately, and does not
        require any buffering.
        """
        self.nextFount = self.ff.flowTo(self.tubeDrain)
        self.assertEquals(self.ff.flowIsPaused, False)
        self.tube.deliver("abc")
        self.assertEquals(self.ff.flowIsPaused, True)


    def test_preDeliveryPausesWhenUpstreamAdded(self):
        """
        If L{_Tube.deliver} has been called already (and the item it was called
        with is still buffered) when L{_Tube.flowingFrom} is called, it will
        pause the fount it is being added to.
        """
        self.tube.deliver('value')
        self.assertEqual(self.ff.flowIsPaused, False)
        self.ff.flowTo(self.tubeDrain)
        self.assertEqual(self.ff.flowIsPaused, True)


    def test_deliverPausesJustOnce(self):
        """
        L{_Tube.deliver} on a tube with an upstream L{IFount} will not call
        its C{pauseFlow} method twice.
        """
        self.test_deliverWithoutDownstreamPauses()
        self.tube.deliver("def")


    def test_addingDownstreamUnpauses(self):
        """
        When a L{_Tube} that is not flowing to a drain yet pauses its upstream
        fount, it will I{resume} its upstream fount when a new downstream
        arrives to un-buffer to.
        """
        self.test_deliverWithoutDownstreamPauses()
        self.nextFount.flowTo(self.fd)
        self.assertEquals(self.ff.flowIsPaused, False)


    def test_pauseFlowWhileUnbuffering(self):
        """
        When a L{_Tube} is unbuffering its inputs received while it didn't have
        a downstream drain, it may be interrupted by its downstream drain
        pausing it.

        If this happens, it should stop delivering.  It also shouldn't pause
        any upstream fount.
        """
        test = self
        class SlowDrain(FakeDrain):
            def __init__(self):
                super(SlowDrain, self).__init__()
                self.ready = True
            def receive(self, item):
                result = super(SlowDrain, self).receive(item)
                self.fount.pauseFlow()
                if not self.ready:
                    test.fail("Received twice.")
                self.ready = False
                return result
            def nextOne(self):
                self.ready = True
                self.fount.resumeFlow()
        sd = SlowDrain()
        nextFount = self.ff.flowTo(self.tubeDrain)
        # Buffer.
        self.tube.deliver(1)
        self.tube.deliver(2)
        self.tube.deliver(3)
        # Unbuffer.
        nextFount.flowTo(sd)
        self.assertEquals(sd.received, [1])
        sd.nextOne()
        self.assertEquals(sd.received, [1, 2])
        sd.nextOne()
        self.assertEquals(sd.received, [1, 2, 3])


    def test_receiveCallsPumpReceived(self):
        """
        L{_Tube.receive} will deliver its input to L{IPump.received} on its
        pump.
        """
        self.tubeDrain.receive("one-item")
        self.assertEquals(self.tube.pump.allReceivedItems,
                          ["one-item"])


    def test_multiStageTubeReturnsLastStage(self):
        """
        XXX explain the way tubes hook together.
        """
        class A(Pump):
            pass
        class B(Pump):
            pass
        a = A()
        b = B()
        ab = cascade(a, b)
        self.ff.flowTo(ab).flowTo(self.fd)
        a.tube.deliver(3)
        b.tube.deliver(4)
        self.assertEquals(self.fd.received, [4])


    def test_flowToWillNotResumeFlowPausedInFlowingFrom(self):
        """
        L{_TubeFount.flowTo} will not call L{_TubeFount.resumeFlow} when
        it's L{IDrain} calls L{IFount.pauseFlow} in L{IDrain.flowingFrom}.
        """
        class PausingDrain(FakeDrain):
            def flowingFrom(self, fount):
                self.fount = fount
                self.fount.pauseFlow()

        self.ff.flowTo(self.tubeDrain).flowTo(PausingDrain())

        self.assertTrue(self.ff.flowIsPaused, "Upstream is not paused.")


    def test_reentrantFlowTo(self):
        """
        An L{IDrain} may call its argument's L{_TubeFount.flowTo} method in
        L{IDrain.flowingFrom} and said fount will be flowing to the new drain.
        """
        test_fd = self.fd

        class ReflowingDrain(FakeDrain):
            def flowingFrom(self, fount):
                self.fount = fount
                self.fount.flowTo(test_fd)

        self.ff.flowTo(self.tubeDrain).flowTo(ReflowingDrain())

        self.assertIdentical(self.tube._tfount.drain, self.fd)

        self.tube.deliver("hello")
        self.assertEqual(self.fd.received, ["hello"])
