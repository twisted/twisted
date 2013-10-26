import os
import signal
from twisted.trial import unittest
from twisted.test.test_process import MockOS, MockSignal
from twisted.scripts import twistd
from twisted.python import runtime


class TwistdSignalHandlingTests(unittest.TestCase):

    def patch_functions(self, mockOS, mockSignal):
        """
        Replace os and signal functions with mock ones
        """
        self.oldKill, self.oldSignal = twistd.os.kill, twistd.signal.signal
        twistd.os.kill = mockOS.kill
        twistd.signal.signal = mockSignal.signal

    def cleanup_functions(self):
        """Get the old functions back"""
        twistd.os.kill = self.oldKill
        twistd.signal.signal = self.oldSignal

    def test_overwriteSIGINTHandler(self):
        """
        Install new sigint handler.
        """
        mockOS = MockOS()
        mockSignal = MockSignal()
        self.patch_functions(mockOS, mockSignal)
        runner = twistd.TwistdApplicationRunner({"nodaemon": True,
                                                 "logfile": "-"})
        self.cleanup_functions()
        self.assertIn((signal.SIGINT, runner.sigInt), mockSignal.signals)

    def test_overwriteSIGTERMHandler(self):
        """
        Install new sigterm handler.
        """
        mockOS = MockOS()
        mockSignal = MockSignal()
        self.patch_functions(mockOS, mockSignal)
        runner = twistd.TwistdApplicationRunner({"nodaemon": True,
                                                 "logfile": "-"})
        self.cleanup_functions()
        self.assertIn((signal.SIGTERM, runner.sigTerm), mockSignal.signals)

    def test_overwriteSIGBREAKHandler(self):
        """
        Install new sigbreak handler.
        """
        mockOS = MockOS()
        mockSignal = MockSignal()
        self.patch_functions(mockOS, mockSignal)
        runner = twistd.TwistdApplicationRunner({"nodaemon": True,
                                                 "logfile": "-"})
        self.cleanup_functions()
        self.assertIn((signal.SIGBREAK, runner.sigBreak), mockSignal.signals)

    def runTwistdInFakeEnviroment(self, replaceRun):
        """
        Run twistd with replaced os, signal and reactor.stop
        functions, also replaced run method
        @param replaceRun: function to replace run.
        """
        mockOS = MockOS()
        mockSignal = MockSignal()
        self.patch_functions(mockOS, mockSignal)
        oldRun = twistd.TwistdApplicationRunner.run
        twistd.TwistdApplicationRunner.run = replaceRun
        oldStop = twistd.reactor.stop
        #don't really stop the reactor
        twistd.reactor.stop = lambda: 0
        twistd.runApp({"nodaemon": True, "logfile": "-"})
        twistd.reactor.stop = oldStop
        twistd.TwistdApplicationRunner.run = oldRun
        self.cleanup_functions()

        return mockOS, mockSignal

    def getExitStatuses(self):
        """
        Returns appropriate reaction to SIGINT, SIGBREAK, SIGTERM in
        that order.
        """
        if runtime.platform.isWindows():
            return (572, 572, 1067)
        else:
            return (signal.SIGINT, -1, signal.SIGTERM)

    def test_exitStatusAfterKillWithSIGINT(self):
        """
        Assert appropriate exit status after sending SIGINT.
        """
        
        mockOS, mockSignal = self.runTwistdInFakeEnviroment(
            twistd.TwistdApplicationRunner.sigInt)

        exitInt = self.getExitStatuses()[0]
        self.assertEquals((signal.SIGINT, 0), mockSignal.signals[-1])
        self.assertEquals(('kill', os.getpid(), exitInt),
                          mockOS.actions[0])

    def test_exitStatusAfterKillWithSIGTERM(self):
        """
        Assert appropriate exit status after sending SIGTERM.
        """
        mockOS, mockSignal = self.runTwistdInFakeEnviroment(
            twistd.TwistdApplicationRunner.sigTerm)

        exitTerm = self.getExitStatuses()[2]
        self.assertEquals((signal.SIGTERM, 0), mockSignal.signals[-1])
        self.assertEquals(('kill', os.getpid(), exitTerm),
                          mockOS.actions[0])

    def test_exitStatusAfterKillWithSIGBREAK(self):
        """
        Assert appropriate exit status after sending SIGBREAK.
        """
        mockOS, mockSignal = self.runTwistdInFakeEnviroment(
            twistd.TwistdApplicationRunner.sigBreak)

        exitBreak = self.getExitStatuses()[1]
        self.assertEquals((signal.SIGBREAK, 0), mockSignal.signals[-1])
        self.assertEquals(('kill', os.getpid(), exitBreak),
                          mockOS.actions[0])

    if not runtime.platform.isWindows():
        test_overwriteSIGBREAKHandler.skip = "SIGBREAK only on Windows."
        test_exitStatusAfterKillWithSIGBREAK.skip = "SIGBREAK only on Windows."
