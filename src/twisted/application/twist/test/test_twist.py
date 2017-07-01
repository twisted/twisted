# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.twist._twist}.
"""

from sys import stdout

from twisted.logger import LogLevel, jsonFileLogObserver
from twisted.test.proto_helpers import MemoryReactor
from ...service import IService, MultiService
from ...runner._exit import ExitStatus
from ...runner._runner import Runner
from ...runner.test.test_runner import DummyExit
from ...twist import _twist
from .._options import TwistOptions
from .._twist import Twist

import twisted.trial.unittest



class TwistTests(twisted.trial.unittest.TestCase):
    """
    Tests for L{Twist}.
    """

    def setUp(self):
        self.patchInstallReactor()


    def patchExit(self):
        """
        Patch L{_twist.exit} so we can capture usage and prevent actual exits.
        """
        self.exit = DummyExit()
        self.patch(_twist, "exit", self.exit)


    def patchInstallReactor(self):
        """
        Patch C{_options.installReactor} so we can capture usage and prevent
        actual installs.
        """
        self.installedReactors = {}

        def installReactor(_, name):
            reactor = MemoryReactor()
            self.installedReactors[name] = reactor
            return reactor

        self.patch(TwistOptions, "installReactor", installReactor)


    def patchStartService(self):
        """
        Patch L{MultiService.startService} so we can capture usage and prevent
        actual starts.
        """
        self.serviceStarts = []

        def startService(service):
            self.serviceStarts.append(service)

        self.patch(MultiService, "startService", startService)


    def test_optionsValidArguments(self):
        """
        L{Twist.options} given valid arguments returns options.
        """
        options = Twist.options(["twist", "web"])

        self.assertIsInstance(options, TwistOptions)


    def test_optionsInvalidArguments(self):
        """
        L{Twist.options} given invalid arguments exits with
        L{ExitStatus.EX_USAGE} and an error/usage message.
        """
        self.patchExit()

        Twist.options(["twist", "--bogus-bagels"])

        self.assertIdentical(self.exit.status, ExitStatus.EX_USAGE)
        self.assertTrue(self.exit.message.startswith("Error: "))
        self.assertTrue(self.exit.message.endswith(
            "\n\n{}".format(TwistOptions())
        ))


    def test_service(self):
        """
        L{Twist.service} returns an L{IService}.
        """
        options = Twist.options(["twist", "web"])  # web should exist
        service = Twist.service(options.plugins["web"], options.subOptions)
        self.assertTrue(IService.providedBy(service))


    def test_startService(self):
        """
        L{Twist.startService} starts the service and registers a trigger to
        stop the service when the reactor shuts down.
        """
        options = Twist.options(["twist", "web"])

        reactor = options["reactor"]
        service = Twist.service(
            plugin=options.plugins[options.subCommand],
            options=options.subOptions,
        )

        self.patchStartService()

        Twist.startService(reactor, service)

        self.assertEqual(self.serviceStarts, [service])
        self.assertEqual(
            reactor.triggers["before"]["shutdown"],
            [(service.stopService, (), {})]
        )


    def test_run(self):
        """
        L{Twist.run} runs the runner with arguments corresponding to the given
        options.
        """
        argsSeen = []

        self.patch(
            Runner, "__init__", lambda self, **args: argsSeen.append(args)
        )
        self.patch(
            Runner, "run", lambda self: None
        )

        twistOptions = Twist.options([
            "twist", "--reactor=default", "--log-format=json", "web"
        ])
        Twist.run(twistOptions)

        self.assertEqual(len(argsSeen), 1)
        self.assertEqual(
            argsSeen[0],
            dict(
                reactor=self.installedReactors["default"],
                defaultLogLevel=LogLevel.info,
                logFile=stdout,
                fileLogObserverFactory=jsonFileLogObserver,
            )
        )


    def test_main(self):
        """
        L{Twist.main} runs the runner with arguments corresponding to the given
        command line arguments.
        """
        self.patchStartService()

        runners = []

        class Runner(object):
            def __init__(self, **kwargs):
                self.args = kwargs
                self.runs = 0
                runners.append(self)

            def run(self):
                self.runs += 1

        self.patch(_twist, "Runner", Runner)

        Twist.main([
            "twist", "--reactor=default", "--log-format=json", "web"
        ])

        self.assertEqual(len(self.serviceStarts), 1)
        self.assertEqual(len(runners), 1)
        self.assertEqual(
            runners[0].args,
            dict(
                reactor=self.installedReactors["default"],
                defaultLogLevel=LogLevel.info,
                logFile=stdout,
                fileLogObserverFactory=jsonFileLogObserver,
            )
        )
        self.assertEqual(runners[0].runs, 1)
