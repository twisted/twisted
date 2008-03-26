# Copyright (c) 2007-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

import os
import sys
import cPickle

from twisted.trial import unittest

from twisted.application import service, app
from twisted.scripts import twistd
from twisted.python import log

try:
    import profile
except ImportError:
    profile = None

try:
    import hotshot
    import hotshot.stats
except (ImportError, SystemExit):
    # For some reasons, hotshot.stats seems to raise SystemExit on some
    # distributions, probably when considered non-free.  See the import of
    # this module in twisted.application.app for more details.
    hotshot = None

try:
    import cProfile
    import pstats
except ImportError:
    cProfile = None



class MockServiceMaker(object):
    """
    A non-implementation of L{twisted.application.service.IServiceMaker}.
    """
    tapname = 'ueoa'

    def makeService(self, options):
        """
        Take a L{usage.Options} instance and return a
        L{service.IService} provider.
        """
        self.options = options
        self.service = service.Service()
        return self.service



class CrippledApplicationRunner(twistd._SomeApplicationRunner):
    """
    An application runner that cripples the platform-specific runner and
    nasty side-effect-having code so that we can use it without actually
    running any environment-affecting code.
    """
    def preApplication(self):
        pass

    def postApplication(self):
        pass

    def startLogging(self, observer):
        pass



class ServerOptionsTest(unittest.TestCase):
    """
    Non-platform-specific tests for the pltaform-specific ServerOptions class.
    """

    def test_postOptionsSubCommandCausesNoSave(self):
        """
        postOptions should set no_save to True when a subcommand is used.
        """
        config = twistd.ServerOptions()
        config.subCommand = 'ueoa'
        config.postOptions()
        self.assertEquals(config['no_save'], True)


    def test_postOptionsNoSubCommandSavesAsUsual(self):
        """
        If no sub command is used, postOptions should not touch no_save.
        """
        config = twistd.ServerOptions()
        config.postOptions()
        self.assertEquals(config['no_save'], False)


    def test_reportProfileDeprecation(self):
        """
        Check that the --report-profile option prints a C{DeprecationWarning}.
        """
        config = twistd.ServerOptions()
        self.assertWarns(
            DeprecationWarning, "--report-profile option is deprecated and "
            "a no-op since Twisted 8.0.", app.__file__,
            config.parseOptions, ["--report-profile", "foo"])



class TapFileTest(unittest.TestCase):
    """
    Test twistd-related functionality that requires a tap file on disk.
    """

    def setUp(self):
        """
        Create a trivial Application and put it in a tap file on disk.
        """
        self.tapfile = self.mktemp()
        cPickle.dump(service.Application("Hi!"), file(self.tapfile, 'wb'))


    def test_createOrGetApplicationWithTapFile(self):
        """
        Ensure that the createOrGetApplication call that 'twistd -f foo.tap'
        makes will load the Application out of foo.tap.
        """
        config = twistd.ServerOptions()
        config.parseOptions(['-f', self.tapfile])
        application = CrippledApplicationRunner(config).createOrGetApplication()
        self.assertEquals(service.IService(application).name, 'Hi!')



class TestApplicationRunner(app.ApplicationRunner):
    """
    An ApplicationRunner which tracks the environment in which its
    methods are called.
    """
    def preApplication(self):
        self.order = ["pre"]
        self.hadApplicationPreApplication = hasattr(self, 'application')


    def getLogObserver(self):
        self.order.append("log")
        self.hadApplicationLogObserver = hasattr(self, 'application')
        return lambda events: None


    def startLogging(self, observer):
        pass


    def postApplication(self):
        self.order.append("post")
        self.hadApplicationPostApplication = hasattr(self, 'application')



class ApplicationRunnerTest(unittest.TestCase):
    """
    Non-platform-specific tests for the platform-specific ApplicationRunner.
    """
    def setUp(self):
        config = twistd.ServerOptions()
        self.serviceMaker = MockServiceMaker()
        # Set up a config object like it's been parsed with a subcommand
        config.loadedPlugins = {'test_command': self.serviceMaker}
        config.subOptions = object()
        config.subCommand = 'test_command'
        self.config = config


    def test_applicationRunnerGetsCorrectApplication(self):
        """
        Ensure that a twistd plugin gets used in appropriate ways: it
        is passed its Options instance, and the service it returns is
        added to the application.
        """
        arunner = CrippledApplicationRunner(self.config)
        arunner.run()

        self.assertIdentical(
            self.serviceMaker.options, self.config.subOptions,
            "ServiceMaker.makeService needs to be passed the correct "
            "sub Command object.")
        self.assertIdentical(
            self.serviceMaker.service,
            service.IService(arunner.application).services[0],
            "ServiceMaker.makeService's result needs to be set as a child "
            "of the Application.")


    def test_preAndPostApplication(self):
        """
        Test thet preApplication and postApplication methods are
        called by ApplicationRunner.run() when appropriate.
        """
        s = TestApplicationRunner(self.config)
        s.run()
        self.failIf(s.hadApplicationPreApplication)
        self.failUnless(s.hadApplicationPostApplication)
        self.failUnless(s.hadApplicationLogObserver)
        self.assertEquals(s.order, ["pre", "log", "post"])


    def test_stdoutLogObserver(self):
        """
        Verify that if C{'-'} is specified as the log file, stdout is used.
        """
        self.config.parseOptions(["--logfile", "-", "--nodaemon"])
        runner = CrippledApplicationRunner(self.config)
        observerMethod = runner.getLogObserver()
        observer = observerMethod.im_self
        self.failUnless(isinstance(observer, log.FileLogObserver))
        writeMethod = observer.write
        fileObj = writeMethod.__self__
        self.assertIdentical(fileObj, sys.stdout)


    def test_fileLogObserver(self):
        """
        Verify that if a string other than C{'-'} is specified as the log file,
        the file with that name is used.
        """
        logfilename = os.path.abspath(self.mktemp())
        self.config.parseOptions(["--logfile", logfilename])
        runner = CrippledApplicationRunner(self.config)
        observerMethod = runner.getLogObserver()
        observer = observerMethod.im_self
        self.failUnless(isinstance(observer, log.FileLogObserver))
        writeMethod = observer.write
        fileObj = writeMethod.im_self
        self.assertEqual(fileObj.path, logfilename)



class DummyReactor(object):
    """
    A dummy reactor, only providing a C{run} method and checking that it
    has been called.

    @ivar called: if C{run} has been called or not.
    @type called: C{bool}
    """
    called = False

    def run(self):
        """
        A fake run method, checking that it's been called one and only time.
        """
        if self.called:
            raise RuntimeError("Already called")
        self.called = True



class AppProfilingTestCase(unittest.TestCase):
    """
    Tests for L{app.AppProfiler}.
    """

    def test_profile(self):
        """
        L{app.ProfileRunner.run} should call the C{run} method of the reactor
        and save profile data in the specified file.
        """
        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "profile"
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        profiler.run(reactor)

        self.assertTrue(reactor.called)
        data = file(config["profile"]).read()
        self.assertIn("DummyReactor.run", data)
        self.assertIn("function calls", data)

    if profile is None:
        test_profile.skip = "profile module not available"


    def test_profileSaveStats(self):
        """
        With the C{savestats} option specified, L{app.ProfileRunner.run}
        should save the raw stats object instead of a summary output.
        """
        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "profile"
        config["savestats"] = True
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        profiler.run(reactor)

        self.assertTrue(reactor.called)
        data = file(config["profile"]).read()
        self.assertIn("DummyReactor.run", data)
        self.assertNotIn("function calls", data)

    if profile is None:
        test_profileSaveStats.skip = "profile module not available"


    def test_withoutProfile(self):
        """
        When the C{profile} module is not present, L{app.ProfilerRunner.run}
        should raise a C{SystemExit} exception.
        """
        savedModules = sys.modules.copy()

        config = twistd.ServerOptions()
        config["profiler"] = "profile"
        profiler = app.AppProfiler(config)

        sys.modules["profile"] = None
        try:
            self.assertRaises(SystemExit, profiler.run, None)
        finally:
            sys.modules.clear()
            sys.modules.update(savedModules)


    def test_profilePrintStatsError(self):
        """
        When an error happens during the print of the stats, C{sys.stdout}
        should be restored to its initial value.
        """
        class ErroneousProfile(profile.Profile):
            def print_stats(self):
                raise RuntimeError("Boom")
        self.patch(profile, "Profile", ErroneousProfile)

        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "profile"
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        oldStdout = sys.stdout
        self.assertRaises(RuntimeError, profiler.run, reactor)
        self.assertIdentical(sys.stdout, oldStdout)

    if profile is None:
        test_profilePrintStatsError.skip = "profile module not available"


    def test_hotshot(self):
        """
        L{app.HotshotRunner.run} should call the C{run} method of the reactor
        and save profile data in the specified file.
        """
        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "hotshot"
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        profiler.run(reactor)

        self.assertTrue(reactor.called)
        data = file(config["profile"]).read()
        self.assertIn("run", data)
        self.assertIn("function calls", data)

    if hotshot is None:
        test_hotshot.skip = "hotshot module not available"


    def test_hotshotSaveStats(self):
        """
        With the C{savestats} option specified, L{app.HotshotRunner.run} should
        save the raw stats object instead of a summary output.
        """
        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "hotshot"
        config["savestats"] = True
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        profiler.run(reactor)

        self.assertTrue(reactor.called)
        data = file(config["profile"]).read()
        self.assertIn("hotshot-version", data)
        self.assertIn("run", data)
        self.assertNotIn("function calls", data)

    if hotshot is None:
        test_hotshotSaveStats.skip = "hotshot module not available"


    def test_withoutHotshot(self):
        """
        When the C{hotshot} module is not present, L{app.HotshotRunner.run}
        should raise a C{SystemExit} exception and log the C{ImportError}.
        """
        savedModules = sys.modules.copy()
        sys.modules["hotshot"] = None

        config = twistd.ServerOptions()
        config["profiler"] = "hotshot"
        profiler = app.AppProfiler(config)
        try:
            self.assertRaises(SystemExit, profiler.run, None)
        finally:
            sys.modules.clear()
            sys.modules.update(savedModules)


    def test_nothotshotDeprecation(self):
        """
        Check that switching on the C{nothotshot} option produces a warning and
        sets the profiler to B{profile}.
        """
        config = twistd.ServerOptions()
        config['nothotshot'] = True
        profiler = self.assertWarns(DeprecationWarning,
            "The --nothotshot option is deprecated. Please specify the "
            "profiler name using the --profiler option",
            app.__file__, app.AppProfiler, config)
        self.assertEquals(profiler.profiler, "profile")


    def test_hotshotPrintStatsError(self):
        """
        When an error happens while printing the stats, C{sys.stdout}
        should be restored to its initial value.
        """
        import pstats
        class ErroneousStats(pstats.Stats):
            def print_stats(self):
                raise RuntimeError("Boom")
        self.patch(pstats, "Stats", ErroneousStats)

        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "hotshot"
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        oldStdout = sys.stdout
        self.assertRaises(RuntimeError, profiler.run, reactor)
        self.assertIdentical(sys.stdout, oldStdout)

    if hotshot is None:
        test_hotshotPrintStatsError.skip = "hotshot module not available"


    def test_cProfile(self):
        """
        L{app.CProfileRunner.run} should call the C{run} method of the
        reactor and save profile data in the specified file.
        """
        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "cProfile"
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        profiler.run(reactor)

        self.assertTrue(reactor.called)
        data = file(config["profile"]).read()
        self.assertIn("run", data)
        self.assertIn("function calls", data)

    if cProfile is None:
        test_cProfile.skip = "cProfile module not available"


    def test_cProfileSaveStats(self):
        """
        With the C{savestats} option specified,
        L{app.CProfileRunner.run} should save the raw stats object
        instead of a summary output.
        """
        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "cProfile"
        config["savestats"] = True
        profiler = app.AppProfiler(config)
        reactor = DummyReactor()

        profiler.run(reactor)

        self.assertTrue(reactor.called)
        data = file(config["profile"]).read()
        self.assertIn("run", data)

    if cProfile is None:
        test_cProfileSaveStats.skip = "cProfile module not available"


    def test_withoutCProfile(self):
        """
        When the C{cProfile} module is not present,
        L{app.CProfileRunner.run} should raise a C{SystemExit}
        exception and log the C{ImportError}.
        """
        savedModules = sys.modules.copy()
        sys.modules["cProfile"] = None

        config = twistd.ServerOptions()
        config["profiler"] = "cProfile"
        profiler = app.AppProfiler(config)
        try:
            self.assertRaises(SystemExit, profiler.run, None)
        finally:
            sys.modules.clear()
            sys.modules.update(savedModules)


    def test_unknownProfiler(self):
        """
        Check that L{app.AppProfiler} raises L{SystemExit} when given an
        unknown profiler name.
        """
        config = twistd.ServerOptions()
        config["profile"] = self.mktemp()
        config["profiler"] = "foobar"

        error = self.assertRaises(SystemExit, app.AppProfiler, config)
        self.assertEquals(str(error), "Unsupported profiler name: foobar")


    def test_oldRunWithProfiler(self):
        """
        L{app.runWithProfiler} should print a C{DeprecationWarning} pointing
        at L{AppProfiler}.
        """
        class DummyProfiler(object):
            called = False
            def run(self, reactor):
                self.called = True
        profiler = DummyProfiler()
        self.patch(app, "AppProfiler", lambda conf: profiler)

        def runWithProfiler():
            return app.runWithProfiler(DummyReactor(), {})

        self.assertWarns(DeprecationWarning,
                "runWithProfiler is deprecated since Twisted 8.0. "
                "Use ProfileRunner instead.", __file__,
                runWithProfiler)
        self.assertTrue(profiler.called)


    def test_oldRunWithHotshot(self):
        """
        L{app.runWithHotshot} should print a C{DeprecationWarning} pointing
        at L{AppProfiler}.
        """
        class DummyProfiler(object):
            called = False
            def run(self, reactor):
                self.called = True
        profiler = DummyProfiler()
        self.patch(app, "AppProfiler", lambda conf: profiler)

        def runWithHotshot():
            return app.runWithHotshot(DummyReactor(), {})

        self.assertWarns(DeprecationWarning,
                "runWithHotshot is deprecated since Twisted 8.0. "
                "Use HotshotRunner instead.", __file__,
                runWithHotshot)
        self.assertTrue(profiler.called)
