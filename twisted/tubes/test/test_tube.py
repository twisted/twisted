# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.tubes.tube}.
"""

from zope.interface import implementer
from zope.interface.verify import verifyObject

from twisted.trial.unittest import TestCase
from twisted.tubes.test.util import (TesterPump, FakeFount,
                                     FakeDrain, IFakeInput)
from twisted.tubes.test.util import JustProvidesSwitchable
from twisted.tubes.itube import ISwitchableTube, ISwitchablePump
from twisted.python.failure import Failure
from twisted.tubes.tube import Pump, series, _Pauser
from twisted.tubes.itube import IPause
from twisted.tubes.itube import AlreadyUnpaused
from twisted.tubes.itube import IPump
from zope.interface.declarations import directlyProvides
from twisted.internet.defer import Deferred, succeed


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
        super(FakeFountWithBuffer, self).__init__()
        self.buffer = []


    def bufferUp(self, item):
        self.buffer.append(item)


    def flowTo(self, drain):
        result = super(FakeFountWithBuffer, self).flowTo(drain)
        self._go()
        return result


    def _actuallyResume(self):
        super(FakeFountWithBuffer, self)._actuallyResume()
        self._go()


    def _go(self):
        while not self.flowIsPaused and self.buffer:
            item = self.buffer.pop(0)
            self.drain.receive(item)



class StopperTest(TestCase):
    """
    Tests for L{_Pauser}, helper for someone who wants to implement a thing
    that pauses.
    """

    def test_pauseOnce(self):
        """
        One call to L{_Pauser.pause} will call the actuallyPause callable.
        """
        def pause():
            pause.d += 1
        pause.d = 0
        pauser = _Pauser(pause, None)
        result = pauser.pauseFlow()
        self.assertTrue(verifyObject(IPause, result))
        self.assertEqual(pause.d, 1)


    def test_pauseThenUnpause(self):
        """
        A call to L{_Pauser.pause} followed by a call to the result's
        C{unpause} will call the C{actuallyResume} callable.
        """
        def pause():
            pause.d += 1
        pause.d = 0
        def resume():
            resume.d += 1
        resume.d = 0
        pauser = _Pauser(pause, resume)
        pauser.pauseFlow().unpause()
        self.assertEqual(pause.d, 1)
        self.assertEqual(resume.d, 1)


    def test_secondUnpauseFails(self):
        """
        The second of two consectuive calls to L{IPause.unpause} results in an
        L{AlreadyUnpaused} exception.
        """
        def pause():
            pass
        def resume():
            resume.d += 1
        resume.d = 0
        pauser = _Pauser(pause, resume)
        aPause = pauser.pauseFlow()
        aPause.unpause()
        self.assertRaises(AlreadyUnpaused, aPause.unpause)
        self.assertEqual(resume.d, 1)


    def test_repeatedlyPause(self):
        """
        Multiple calls to L{_Pauser.pause} where not all of the pausers are
        unpaused do not result in any calls to C{actuallyResume}.
        """
        def pause():
            pause.d += 1
        pause.d = 0
        def resume():
            resume.d += 1
        resume.d = 0
        pauser = _Pauser(pause, resume)
        one = pauser.pauseFlow()
        two = pauser.pauseFlow()
        three = pauser.pauseFlow()
        four = pauser.pauseFlow()

        one.unpause()
        two.unpause()
        three.unpause()
        self.assertEqual(pause.d, 1)
        self.assertEqual(resume.d, 0)
        four.unpause()
        self.assertEqual(resume.d, 1)



class PumpTest(TestCase):
    """
    Tests for L{Pump}'s various no-ops.
    """

    def test_provider(self):
        """
        L{Pump} provides L{IPump}.
        """
        self.failUnless(verifyObject(IPump, Pump()))


    def test_noOps(self):
        """
        All of L{Pump}'s implementations of L{IPump} are no-ops.
        """
        # There are no assertions here because there's no reasonable way this
        # test will fail rather than error; however, coverage --branch picks up
        # on methods which haven't been executed and the fact that these
        # methods exist (i.e. for super() to invoke them) is an important
        # property to verify. -glyph

        # TODO: maybe make a policy of this or explain it somewhere other than
        # a comment.  Institutional learning ftw.

        pump = Pump()
        pump.started()
        pump.received(None)
        pump.progressed(None)
        pump.progressed()
        pump.stopped(None)



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
        The L{_Tube} stops its L{Pump} and propagates C{flowStopped} downstream
        upon C{flowStopped}.
        """
        reasons = []
        class Ender(Pump):
            def stopped(self, reason):
                reasons.append(reason)
                yield "conclusion"

        self.ff.flowTo(series(Ender(), self.fd))
        self.assertEquals(reasons, [])
        self.assertEquals(self.fd.received, [])

        stopReason = Failure(ZeroDivisionError())

        self.ff.drain.flowStopped(stopReason)
        self.assertEquals(self.fd.received, ["conclusion"])
        self.assertEquals(len(reasons), 1)
        self.assertIdentical(reasons[0].type, ZeroDivisionError)

        self.assertEqual(self.fd.stopped, [stopReason])


    def test_pumpStoppedDeferredly(self):
        """
        The L{_Tube} stops its L{Pump} and propagates C{flowStopped} downstream
        upon the completion of all L{Deferred}s returned from its L{Pump}'s
        C{stopped} implementation.
        """
        reasons = []
        conclusion = Deferred()
        class SlowEnder(Pump):
            def stopped(self, reason):
                reasons.append(reason)
                yield conclusion

        self.ff.flowTo(series(SlowEnder(), self.fd))
        self.assertEquals(reasons, [])
        self.assertEquals(self.fd.received, [])

        stopReason = Failure(ZeroDivisionError())

        self.ff.drain.flowStopped(stopReason)
        self.assertEquals(self.fd.received, [])
        self.assertEquals(len(reasons), 1)
        self.assertIdentical(reasons[0].type, ZeroDivisionError)
        self.assertEqual(self.fd.stopped, [])

        conclusion.callback("conclusion")
        # Now it's really done.
        self.assertEquals(self.fd.received, ["conclusion"])
        self.assertEqual(self.fd.stopped, [stopReason])


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
        testCase = self

        class Switcher(Pump):
            def received(self, data):
                # Sanity check: this should be the only input ever received.
                testCase.assertEqual(data, "switch")
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


    def test_pumpFlowSwitchingReassembly(self):
        """
        The L{_Tube} of a L{Pump} sends on reassembled data - the return value
        of L{Pump.reassemble} to a newly specified L{Drain}; it is only called
        with un-consumed elements of data (those which have never been passed
        to C{receive}).
        """
        preSwitch = []
        @implementer(ISwitchablePump)
        class ReassemblingPump(Pump):
            def received(self, datum):
                nonBorks = datum.split("BORK")
                return nonBorks

            def reassemble(self, data):
                for element in data:
                    yield '(bork was here)'
                    yield element

        class Switcher(Pump):
            def received(self, data):
                # Sanity check: this should be the only input ever received.
                preSwitch.append(data)
                sourcePump.tube.switch(series(Switchee(), fakeDrain))
                return ()

        class Switchee(Pump):
            def received(self, data):
                yield "switched " + data

        sourcePump = ReassemblingPump()
        fakeDrain = self.fd
        firstDrain = series(sourcePump)
        self.ff.flowTo(firstDrain).flowTo(series(Switcher(), fakeDrain))

        self.ff.drain.receive("beforeBORKto switchee")

        self.assertEqual(preSwitch, ["before"])
        self.assertEqual(self.fd.received, ["switched (bork was here)",
                                            "switched to switchee"])


    def test_pumpFlowSwitchingControlsWhereOutputGoes(self):
        """
        If a tube A with a pump Ap is flowing to a tube B with a switchable
        pump Bp, Ap.received may switch B to a drain C, and C will receive any
        outputs produced by that received call; B (and Bp) will not.
        """
        class Switcher(Pump):
            def received(self, data):
                if data == "switch":
                    yield "switching"
                    destinationPump.tube.switch(series(Switchee(), fakeDrain))
                    yield "switched"
                else:
                    yield data

        class Switchee(Pump):
            def received(self, data):
                yield "switched({})".format(data)

        fakeDrain = self.fd
        destinationPump = PassthruPump()
        # reassemble should not be called, so don't implement it
        directlyProvides(destinationPump, ISwitchablePump)

        firstDrain = series(Switcher(), destinationPump)
        self.ff.flowTo(firstDrain).flowTo(fakeDrain)
        self.ff.drain.receive("before")
        self.ff.drain.receive("switch")
        self.ff.drain.receive("after")
        self.assertEqual(self.fd.received,
                         ["before", "switching",
                          "switched(switched)",
                          "switched(after)"])


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


    def test_flowingFromNoneInitialNoOp(self):
        """
        L{_TubeFount.flowTo}C{(None)} is a no-op when called before
        any other invocations of L{_TubeFount.flowTo}.
        """
        tubeFount = self.ff.flowTo(self.tubeDrain)
        self.assertEquals(tubeFount.drain, None)
        tubeFount.flowTo(None)


    def test_pumpFlowSwitching_ReEntrantResumeReceive(self):
        """
        Switching a pump that is receiving data from a fount which
        synchronously produces some data to C{receive} will ... uh .. work.
        """
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
        destinationPump = PassthruPump()
        # reassemble should not be called, so don't implement it
        directlyProvides(destinationPump, ISwitchablePump)

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
            """
            Reassemble should not be called; don't implement it.
            """

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

        anPause = self.fd.fount.pauseFlow()

        d.callback("hello")
        self.assertEquals(self.fd.received, [])

        anPause.unpause()
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
                if not got:
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
        self.tubeDrain.receive(2)
        self.assertEquals(progged, [None])


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

        myPause = self.ff.flowTo(self.tubeDrain).pauseFlow()
        newFF.flowTo(self.tubeDrain)

        self.assertTrue(newFF.flowIsPaused, "New upstream is not paused.")


    def test_switchingNonSwitchableError(self):
        """
        L{_Tube.switch} on a L{_Tube} without an L{ISwitchablePump} raises
        L{NotImplementedError} with a helpful message.
        """
        nie = self.assertRaises(NotImplementedError, self.tube.switch, None)
        self.assertIn("this tube cannot be switched", str(nie))


    def test_switchableTubeGetsImplemented(self):
        """
        Passing an L{ISwitchablePump} to L{_Tube} will cause it to provide
        L{ISwitchableTube}.
        """

        pump = JustProvidesSwitchable()
        series(pump)
        self.assertTrue(ISwitchableTube.providedBy(pump.tube))


    def test_switchableTubeCanGetUnimplemented(self):
        """
        Passing an L{ISwitchablePump} and then a L{IPump} to L{_Tube} will
        cause it to no longer provide L{ISwitchableTube}.
        """

        pump = JustProvidesSwitchable()
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

        pump = JustProvidesSwitchable()
        series(pump)
        otherPump = JustProvidesSwitchable()
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

        pump = JustProvidesSwitchable()
        series(pump)
        otherPump = TesterPump()
        tube = pump.tube
        tube.pump = otherPump
        thirdPump = JustProvidesSwitchable()
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


    def test_stopFlow(self):
        """
        L{_TubeFount.stopFlow} stops the flow of its L{_Tube}'s upstream fount.
        """
        self.ff.flowTo(series(self.tube, self.fd))
        self.assertEquals(self.ff.flowIsStopped, False)
        self.fd.fount.stopFlow()
        self.assertEquals(self.ff.flowIsStopped, True)


    def test_stopFlowBeforeFlowBegins(self):
        """
        L{_TubeFount.stopFlow} will stop the flow of its L{_Tube}'s upstream
        fount later, when it acquires one, if it's previously been stopped.
        """
        partially = series(self.tube, self.fd)
        self.fd.fount.stopFlow()
        self.ff.flowTo(partially)
        self.assertEquals(self.ff.flowIsStopped, True)
