# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

import os
import sys
import cPickle

from twisted.trial import unittest

from twisted.application import service, app
from twisted.scripts import twistd
from twisted.python import log


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
            "a no-op since Twisted 2.6.", app.__file__,
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
