# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.tube}.
"""

from twisted.trial.unittest import TestCase
from twisted.tubes.test.util import (TesterPump, FakeFount,
                                     FakeDrain, IFakeInput)
from twisted.tubes.test.util import SwitchableTesterPump
from twisted.tubes.itube import ISwitchableTube, ISwitchablePump
from twisted.python.failure import Failure
from twisted.tubes.tube import Pump, series
from twisted.internet.defer import Deferred, succeed

from zope.interface import implementer


class ReprPump(Pump):
    def __repr__(self):
        return '<Pump For Testing>'



class PassthruPump(Pump):
    def received(self, data):
        yield data



class FakeFountWithBuffer(FakeFount):
    """
    Probably this should be replaced with a C{MemoryFount}.
    """
    def __init__(self):
        self.buffer = []


    def bufferUp(self, item):
        self.buffer.append(item)


    def flowTo(self, drain):
        result = super(FakeFountWithBuffer, self).flowTo(drain)
        self._go()
        return result


    def resumeFlow(self):
        super(FakeFountWithBuffer, self).resumeFlow()
        self._go()


    def _go(self):
        while not self.flowIsPaused and self.buffer:
            item = self.buffer.pop(0)
            self.drain.receive(item)



class TubeTest(TestCase):
    """
    Tests for L{series}.
    """

    def setUp(self):
        """
        Create a tube, and a fake drain and fount connected to it.
        """
        self.pump = TesterPump()
        self.tubeDrain = series(self.pump)
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
                yield "greeting"

        self.ff.flowTo(series(Starter(), self.fd))
        self.assertEquals(self.fd.received, ["greeting"])


    def test_pumpStopped(self):
        """
        The L{_Tube} stops its L{Pump} upon C{flowStopped}.
        """
        reasons = []
        class Ender(Pump):
            def stopped(self, reason):
                reasons.append(reason)
                yield "conclusion"

        self.ff.flowTo(series(Ender(), self.fd))
        self.assertEquals(reasons, [])
        self.assertEquals(self.fd.received, [])
        self.ff.drain.flowStopped(Failure(ZeroDivisionError()))
        self.assertEquals(self.fd.received, ["conclusion"])
        self.assertEquals(len(reasons), 1)
        self.assertIdentical(reasons[0].type, ZeroDivisionError)


    def test_pumpFlowSwitching(self):
        """
        The L{_Tube} of a L{Pump} sends on data to a newly specified L{IDrain}
        when its L{ITube.switch} method is called.
        """
        @implementer(ISwitchablePump)
        class SwitchablePassthruPump(PassthruPump):
            def reassemble(self, data):
                return data

        sourcePump = SwitchablePassthruPump()
        fakeDrain = self.fd

        class Switcher(Pump):
            def received(self, data):
                if data == "switch":
                    sourcePump.tube.switch(series(Switchee(), fakeDrain))
                return ()

        class Switchee(Pump):
            def received(self, data):
                yield "switched " + data

        firstDrain = series(sourcePump)

        self.ff.flowTo(firstDrain).flowTo(series(Switcher(), fakeDrain))
        self.ff.drain.receive("switch")
        self.ff.drain.receive("to switchee")
        self.assertEquals(fakeDrain.received, ["switched to switchee"])


    def test_pumpFlowSwitching_WithCheese(self):
        # XXX RENAME
        """
        The L{_Tube} of a L{Pump} sends on reassembled data to a newly
        specified L{Drain}.
        """
        @implementer(ISwitchablePump)
        class ReassemblingPump(Pump):
            def received(self, datum):
                nonBorks = datum.split("BORK")
                return nonBorks

            def reassemble(self, data):
                for element in data:
                    yield 'BORK'
                    yield element

        class Switcher(Pump):
            def received(self, data):
                if data == "switch":
                    sourcePump.tube.switch(series(Switchee(), fakeDrain))
                return ()

        class Switchee(Pump):
            def received(self, data):
                yield "switched " + data

        sourcePump = ReassemblingPump()
        fakeDrain = self.fd
        firstDrain = series(sourcePump)
        self.ff.flowTo(firstDrain).flowTo(series(Switcher(), fakeDrain))

        self.ff.drain.receive("switchBORKto switchee")

        self.assertEquals(self.fd.received, ["switched BORK",
                                             "switched to switchee"])


    def test_pumpFlowSwitching_TheWorks(self):
        # XXX RENAME
        """
        Switching a pump that has never received data works I{just fine} thank
        you very much.
        """
        @implementer(ISwitchablePump)
        class SwitchablePassthruPump(PassthruPump):
            def reassemble(self, data):
                raise NotImplementedError("Should not actually be called.")

        class Switcher(Pump):
            def received(self, data):
                if data == "switch":
                    destinationPump.tube.switch(series(Switchee(), fakeDrain))
                else:
                    return [data]

        class Switchee(Pump):
            def received(self, data):
                yield "switched " + data

        fakeDrain = self.fd
        destinationPump = SwitchablePassthruPump()

        firstDrain = series(Switcher(), destinationPump)
        self.ff.flowTo(firstDrain).flowTo(fakeDrain)
        self.ff.drain.receive("before")
        self.ff.drain.receive("switch")
        self.ff.drain.receive("after")
        self.assertEquals(self.fd.received, ["before", "switched after"])


    def test_initiallyEnthusiasticFountBecomesDisillusioned(self):
        """
        If an L{IFount} provider synchronously calls C{receive} on a
        L{_TubeDrain}, whose corresponding L{_TubeFount} is not flowing to an
        L{IDrain} yet, it will be synchronously paused with
        L{IFount.pauseFlow}; when that L{_TubeFount} then flows to something
        else, the buffer will be unspooled.
        """
        ff = FakeFountWithBuffer()
        ff.bufferUp("something")
        ff.bufferUp("else")
        newDrain = series(PassthruPump())
        # Just making sure.
        self.assertEqual(ff.flowIsPaused, False)
        newFount = ff.flowTo(newDrain)
        self.assertEqual(ff.flowIsPaused, True)
        # "something" should have been un-buffered at this point.
        self.assertEqual(ff.buffer, ["else"])
        newFount.flowTo(self.fd)
        self.assertEqual(ff.buffer, [])
        self.assertEqual(ff.flowIsPaused, False)
        self.assertEqual(self.fd.received, ["something", "else"])


    def test_pumpFlowSwitching_ReEntrantResumeReceive(self):
        """
        Switching a pump that is receiving data from a fount which
        synchronously produces some data to C{receive} will ... uh .. work.
        """

        @implementer(ISwitchablePump)
        class SwitchablePassthruPump(PassthruPump):
            def reassemble(self, data):
                raise NotImplementedError("Should not actually be called.")

        class Switcher(Pump):
            def received(self, data):
                if data == "switch":
                    destinationPump.tube.switch(series(Switchee(), fakeDrain))
                    return None
                else:
                    return [data]

        class Switchee(Pump):
            def received(self, data):
                yield "switched " + data

        fakeDrain = self.fd
        destinationPump = SwitchablePassthruPump()

        firstDrain = series(Switcher(), destinationPump)

        ff = FakeFountWithBuffer()
        ff.bufferUp("before")
        ff.bufferUp("switch")
        ff.bufferUp("after")
        ff.flowTo(firstDrain).flowTo(fakeDrain)
        self.assertEquals(self.fd.received, ["before", "switched after"])


    def test_pumpFlowSwitching_LotsOfStuffAtOnce(self):
        """
        If a pump returns a sequence of multiple things, great.
        """
        # TODO: docstring.
        @implementer(ISwitchablePump)
        class SwitchablePassthruPump(PassthruPump):
            def reassemble(self, data):
                raise NotImplementedError("Should not actually be called.")

        class Multiplier(Pump):
            def received(self, datums):
                return datums

        class Switcher(Pump):
            def received(self, data):
                if data == "switch":
                    destinationPump.tube.switch(series(Switchee(), fakeDrain))
                    return None
                else:
                    return [data]

        class Switchee(Pump):
            def received(self, data):
                yield "switched " + data

        fakeDrain = self.fd
        destinationPump = SwitchablePassthruPump()

        firstDrain = series(Multiplier(), Switcher(), destinationPump)

        self.ff.flowTo(firstDrain).flowTo(fakeDrain)
        self.ff.drain.receive(["before", "switch", "after"])
        self.assertEquals(self.fd.received, ["before", "switched after"])


    def test_pumpYieldsFiredDeferred(self):
        """
        When a pump yields a fired L{Deferred} its result is synchronously
        delivered.
        """

        class SucceedingPump(Pump):
            def received(self, data):
                yield succeed(''.join(reversed(data)))

        fakeDrain = self.fd
        self.ff.flowTo(series(SucceedingPump())).flowTo(fakeDrain)
        self.ff.drain.receive("hello")
        self.assertEquals(self.fd.received, ["olleh"])


    def test_pumpYieldsUnfiredDeferred(self):
        """
        When a pump yields an unfired L{Deferred} its result is asynchronously
        delivered.
        """

        d = Deferred()

        class WaitingPump(Pump):
            def received(self, data):
                yield d

        fakeDrain = self.fd
        self.ff.flowTo(series(WaitingPump())).flowTo(fakeDrain)
        self.ff.drain.receive("ignored")
        self.assertEquals(self.fd.received, [])

        d.callback("hello")

        self.assertEquals(self.fd.received, ["hello"])


    def test_pumpYieldsMultipleDeferreds(self):
        """
        When a pump yields multiple deferreds their results should be delivered
        in order.
        """

        d = Deferred()

        class MultiDeferredPump(Pump):
            didYield = False
            def received(self, data):
                yield d
                MultiDeferredPump.didYield = True
                yield succeed("goodbye")

        fakeDrain = self.fd
        self.ff.flowTo(series(MultiDeferredPump())).flowTo(fakeDrain)
        self.ff.drain.receive("ignored")
        self.assertEquals(self.fd.received, [])

        d.callback("hello")

        self.assertEquals(self.fd.received, ["hello", "goodbye"])


    def test_pumpYieldedDeferredFiresWhileFlowIsPaused(self):
        """
        When a L{Pump} yields an L{Deferred} and that L{Deferred} fires when
        the L{_TubeFount} is paused it should buffer it's result and deliver it
        when L{_TubeFount.resumeFlow} is called.
        """
        d = Deferred()

        class DeferredPump(Pump):
            def received(self, data):
                yield d

        fakeDrain = self.fd
        self.ff.flowTo(series(DeferredPump())).flowTo(fakeDrain)
        self.ff.drain.receive("ignored")

        self.fd.fount.pauseFlow()

        d.callback("hello")
        self.assertEquals(self.fd.received, [])

        self.fd.fount.resumeFlow()
        self.assertEquals(self.fd.received, ["hello"])


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
        L{_TubeDrain.receive} will call C{pump.received} and synthesize a fake
        "0.5" progress result if L{None} is returned.
        """
        got = []
        class ReceivingPump(Pump):
            def received(self, item):
                got.append(item)
        self.tube.pump = ReceivingPump()
        self.tubeDrain.receive("sample item")
        self.assertEqual(got, ["sample item"])


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
        method if its L{Pump} does not produce any output.
        """
        got = []
        class ProgressingPump(Pump):
            def progressed(self, amount=None):
                got.append(amount)
        self.ff.flowTo(self.tubeDrain).flowTo(series(ProgressingPump()))
        self.tubeDrain.receive(2)
        self.assertEquals(got, [None])


    def test_tubeReceiveDoesntRelayUnnecessaryProgress(self):
        """
        L{_TubeDrain.receive} will not call its downstream L{IDrain}'s
        C{progress} method if its L{Pump} I{does} produce some output, because
        the progress notification is redundant in that case; input was
        received, output was sent on.  A call to C{progress} would imply that
        I{more} data had come in, and that isn't necessarily true.
        """
        progged = []
        got = []
        class ReceivingPump(Pump):
            def received(self, item):
                yield item + 1
        class ProgressingPump(Pump):
            def progressed(self, amount=None):
                progged.append(amount)
            def received(self, item):
                got.append(item)
        self.tube.pump = ReceivingPump()
        self.ff.flowTo(self.tubeDrain).flowTo(series(ProgressingPump()))
        self.tubeDrain.receive(2)
        # sanity check
        self.assertEquals(got, [3])
        self.assertEquals(progged, [])


    def test_flowFromTypeCheck(self):
        """
        L{_Tube.flowingFrom} checks the type of its input.  If it doesn't match
        (both are specified explicitly, and they don't match).
        """
        class ToPump(Pump):
            inputType = IFakeInput
        self.tube.pump = ToPump()
        self.failUnlessRaises(TypeError, self.ff.flowTo, self.tubeDrain)


    def test_receiveIterableDeliversDownstream(self):
        """
        When L{Pump.received} yields a value, L{_Tube} will call L{receive} on
        its downstream drain.
        """
        self.ff.flowTo(series(PassthruPump())).flowTo(self.fd)
        self.ff.drain.receive(7)
        self.assertEquals(self.fd.received, [7])


    def test_receiveCallsPumpReceived(self):
        """
        L{_TubeDrain.receive} will send its input to L{IPump.received} on its
        pump.
        """
        self.tubeDrain.receive("one-item")
        self.assertEquals(self.tube.pump.allReceivedItems, ["one-item"])


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

        self.ff.flowTo(series(PassthruPump())).flowTo(ReflowingDrain())

        self.ff.drain.receive("hello")
        self.assertEqual(self.fd.received, ["hello"])


    def test_drainPausesFlowWhenPreviouslyPaused(self):
        """
        L{_TubeDrain.flowingFrom} will pause its fount if its L{_TubeFount} was
        previously paused.
        """
        newFF = FakeFount()

        self.ff.flowTo(self.tubeDrain).pauseFlow()
        newFF.flowTo(self.tubeDrain)

        self.assertTrue(newFF.flowIsPaused, "New upstream is not paused.")


    def test_switchableTubeGetsImplemented(self):
        """
        Passing an L{ISwitchablePump} to L{_Tube} will cause it to provide
        L{ISwitchableTube}.
        """

        pump = SwitchableTesterPump()
        series(pump)
        self.assertTrue(ISwitchableTube.providedBy(pump.tube))


    def test_switchableTubeCanGetUnimplemented(self):
        """
        Passing an L{ISwitchablePump} and then a L{IPump} to L{_Tube} will
        cause it to no longer provide L{ISwitchableTube}.
        """

        pump = SwitchableTesterPump()
        series(pump)
        otherPump = TesterPump()
        tube = pump.tube
        tube.pump = otherPump
        self.assertFalse(ISwitchableTube.providedBy(tube))


    def test_switchableTubeCanStayImplemented(self):
        """
        Passing an L{ISwitchablePump} and then an L{ISwitchablePump} to
        L{_Tube} will cause it to still provide L{ISwitchableTube}.
        """

        pump = SwitchableTesterPump()
        series(pump)
        otherPump = SwitchableTesterPump()
        tube = pump.tube
        tube.pump = otherPump
        self.assertTrue(ISwitchableTube.providedBy(tube))


    def test_switchableTubeCanStayUnimplemented(self):
        """
        Passing an L{IPump} and then an L{IPump} to L{_Tube} will cause it to
        still not provide L{ISwitchableTube}.
        """

        pump = TesterPump()
        series(pump)
        otherPump = TesterPump()
        tube = pump.tube
        tube.pump = otherPump
        self.assertFalse(ISwitchableTube.providedBy(tube))


    def test_switchableTubeCanGetReimplemented(self):
        """
        Passing an L{ISwitchablePump} and then a L{IPump} and then an
        L{ISwitchablePump} again to L{_Tube} will cause it to provide
        L{ISwitchableTube}.
        """

        pump = SwitchableTesterPump()
        series(pump)
        otherPump = TesterPump()
        tube = pump.tube
        tube.pump = otherPump
        thirdPump = SwitchableTesterPump()
        tube.pump = thirdPump
        self.assertTrue(ISwitchableTube.providedBy(tube))


    def test_tubeDrainRepr(self):
        """
        repr for L{_TubeDrain} includes a reference to its pump.
        """

        self.assertEqual(repr(series(ReprPump())),
                         '<Drain for <Pump For Testing>>')


    def test_tubeFountRepr(self):
        """
        repr for L{_TubeFount} includes a reference to its pump.
        """

        fount = FakeFount()

        self.assertEqual(repr(fount.flowTo(series(ReprPump()))),
                         '<Fount for <Pump For Testing>>')


    def test_tubeRepr(self):
        """
        repr for L{_Tube} includes a reference to its pump.
        """

        pump = ReprPump()
        series(pump)

        self.assertEqual(repr(pump.tube), '<Tube for <Pump For Testing>>')


