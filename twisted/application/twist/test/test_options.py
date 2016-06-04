# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.runner._runner}.
"""

from sys import stdout, stderr

from twisted.copyright import version
from twisted.python.usage import UsageError
from twisted.logger import LogLevel, textFileLogObserver, jsonFileLogObserver
from ...service import ServiceMaker
from ...runner import ExitStatus
from ...runner.test.test_runner import DummyExit
from ...twist import _options
from .._options import TwistOptions

import twisted.trial.unittest



class OptionsTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{TwistOptions}.
    """

    def patchExit(self):
        # Patch exit so we can capture usage and prevent actual exits.
        self.exit = DummyExit()
        self.patch(_options, "exit", self.exit)


    def patchOpen(self):
        self.opened = []

        def fakeOpen(name, mode=None):
            self.opened.append((name, mode))
            return NotImplemented

        self.patch(_options, "openFile", fakeOpen)


    def test_synopsis(self):
        """
        L{TwistOptions.getSynopsis} appends arguments.
        """
        options = TwistOptions()

        self.assertTrue(
            options.getSynopsis().endswith(" plugin [plugin_options]")
        )


    def test_version(self):
        """
        L{TwistOptions.opt_version} exits with L{ExitStatus.EX_OK} and prints
        the version.
        """
        self.patchExit()

        options = TwistOptions()
        options.opt_version()

        self.assertEquals(self.exit.status, ExitStatus.EX_OK)
        self.assertEquals(self.exit.message, version)


    def test_reactor(self):
        """
        L{TwistOptions.opt_reactor} sets the reactor name.
        """
        options = TwistOptions()
        options.opt_reactor("fission")

        self.assertEquals(options["reactorName"], "fission")


    def test_installReactor(self):
        """
        L{TwistOptions.installReactor} installs the chosen reactor.
        """
        # Patch installReactor so we can capture usage and prevent installation.
        installed = []
        self.patch(
            _options, "installReactor", lambda name: installed.append(name)
        )

        options = TwistOptions()
        options.opt_reactor("fusion")
        options.installReactor()

        self.assertEqual(installed, ["fusion"])


    def test_logLevelValid(self):
        """
        L{TwistOptions.opt_log_level} sets the corresponding log level.
        """
        options = TwistOptions()
        options.opt_log_level("warn")

        self.assertIdentical(options["logLevel"], LogLevel.warn)


    def test_logLevelInvalid(self):
        """
        L{TwistOptions.opt_log_level} with an invalid log level name raises
        UsageError.
        """
        options = TwistOptions()

        self.assertRaises(UsageError, options.opt_log_level, "cheese")


    def _testLogFile(self, name, expectedStream):
        options = TwistOptions()
        options.opt_log_file(name)

        self.assertIdentical(options["logFile"], expectedStream)


    def test_logFileStdout(self):
        """
        L{TwistOptions.opt_log_file} given C{"-"} as a file name uses stdout.
        """
        self._testLogFile("-", stdout)


    def test_logFileStderr(self):
        """
        L{TwistOptions.opt_log_file} given C{"+"} as a file name uses stderr.
        """
        self._testLogFile("+", stderr)


    def test_logFileNamed(self):
        """
        L{TwistOptions.opt_log_file} opens the given file name in append mode.
        """
        self.patchOpen()

        options = TwistOptions()
        options.opt_log_file("mylog")

        self.assertEqual([("mylog", "a")], self.opened)


    def _testLogFormat(self, format, expectedObserver):
        options = TwistOptions()
        options.opt_log_format(format)

        self.assertIdentical(
            options["fileLogObserverFactory"], expectedObserver
        )
        self.assertEqual(options["logFormat"], format)


    def test_logFormatText(self):
        """
        L{TwistOptions.opt_log_format} given C{"text"} uses a
        L{textFileLogObserver}.
        """
        self._testLogFormat("text", textFileLogObserver)


    def test_logFormatJSON(self):
        """
        L{TwistOptions.opt_log_format} given C{"text"} uses a
        L{textFileLogObserver}.
        """
        self._testLogFormat("json", jsonFileLogObserver)


    def test_logFormatInvalid(self):
        """
        L{TwistOptions.opt_log_format} given an invalid format name raises
        L{UsageError}.
        """
        options = TwistOptions()

        self.assertRaises(UsageError, options.opt_log_format, "frommage")


    def test_selectDefaultLogObserverNoOverride(self):
        """
        L{TwistOptions.selectDefaultLogObserver} will not override an already
        selected observer.
        """
        self.patchOpen()

        options = TwistOptions()
        options.opt_log_format("text")  # Ask for text
        options.opt_log_file("queso")   # File, not a tty
        options.selectDefaultLogObserver()

        # Because we didn't select a file that is a tty, the default is JSON,
        # but since we asked for text, we should get text.
        self.assertIdentical(
            options["fileLogObserverFactory"], textFileLogObserver
        )
        self.assertEqual(options["logFormat"], "text")


    def test_selectDefaultLogObserverDefaultWithTTY(self):
        """
        L{TwistOptions.selectDefaultLogObserver} will not override an already
        selected observer.
        """
        options = TwistOptions()
        options.opt_log_file("-")  # stdout, a tty
        options.selectDefaultLogObserver()

        self.assertIdentical(
            options["fileLogObserverFactory"], textFileLogObserver
        )
        self.assertEqual(options["logFormat"], "text")


    def test_selectDefaultLogObserverDefaultWithoutTTY(self):
        """
        L{TwistOptions.selectDefaultLogObserver} will not override an already
        selected observer.
        """
        self.patchOpen()

        options = TwistOptions()
        options.opt_log_file("queso")  # File, not a tty
        options.selectDefaultLogObserver()

        self.assertIdentical(
            options["fileLogObserverFactory"], jsonFileLogObserver
        )
        self.assertEqual(options["logFormat"], "json")


    def test_pluginsType(self):
        """
        L{TwistOptions.plugins} is a mapping of available plug-ins.
        """
        options = TwistOptions()
        plugins = options.plugins

        for name in plugins:
            self.assertIsInstance(name, str)
            self.assertIsInstance(plugins[name], ServiceMaker)


    def test_pluginsIncludeWeb(self):
        """
        L{TwistOptions.plugins} includes a C{"web"} plug-in.
        This is an attempt to verify that something we expect to be in the list
        is in there without enumerating all of the built-in plug-ins.
        """
        options = TwistOptions()

        self.assertIn("web", options.plugins)


    def test_subCommandsType(self):
        """
        L{TwistOptions.subCommands} is an iterable of tuples as expected by
        L{twisted.python.usage.Options}.
        """
        options = TwistOptions()

        for name, shortcut, parser, doc in options.subCommands:
            self.assertIsInstance(name, str)
            self.assertIdentical(shortcut, None)
            self.assertTrue(callable(parser))
            self.assertIsInstance(doc, str)


    def test_subCommandsIncludeWeb(self):
        """
        L{TwistOptions.subCommands} includes a sub-command for every plug-in.
        """
        options = TwistOptions()

        plugins = set(options.plugins)
        subCommands = set(
            name for name, shortcut, parser, doc in options.subCommands
        )

        self.assertEqual(subCommands, plugins)


    def test_postOptionsNoSubCommand(self):
        """
        L{TwistOptions.postOptions} raises L{UsageError} is it has no
        sub-command.
        """
        options = TwistOptions()

        self.assertRaises(UsageError, options.postOptions)
