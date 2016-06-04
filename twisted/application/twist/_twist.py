# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Run a Twisted application.
"""

import sys

from twisted.python.usage import UsageError
from ..service import Application, IService
from ..runner import Runner, RunnerOptions, exit, ExitStatus
from ._options import TwistOptions



class Twist(object):
    """
    Run a Twisted application.
    """

    @staticmethod
    def options(argv):
        """
        Parse command line options.
        """
        options = TwistOptions()

        try:
            options.parseOptions(argv[1:])
        except UsageError as e:
            exit(ExitStatus.EX_USAGE, "Error: {}\n\n{}".format(e, options))

        return options


    @staticmethod
    def service(plugin, options):
        """
        Create the application service.
        """
        service = plugin.makeService(options)
        application = Application(plugin.tapname)
        service.setServiceParent(application)

        return IService(application)


    @staticmethod
    def startService(reactor, service):
        # Start the service
        service.startService()

        # Ask the reactor to stop the service before shutting down
        reactor.addSystemEventTrigger(
            "before", "shutdown", service.stopService
        )


    @staticmethod
    def runnerOptions(twistOptions):
        """
        Take options obtained from command line and configure options for the
        application runner.
        """
        runnerOptions = {}

        for runnerOpt, twistOpt in (
            (RunnerOptions.reactor, "reactor"),
            (RunnerOptions.defaultLogLevel, "logLevel"),
            (RunnerOptions.logFile, "logFile"),
            (RunnerOptions.fileLogObserverFactory, "fileLogObserverFactory"),
        ):
            runnerOptions[runnerOpt] = twistOptions[twistOpt]

        return runnerOptions


    @staticmethod
    def run(runnerOptions):
        runner = Runner(runnerOptions)
        runner.run()


    @classmethod
    def main(cls, argv=sys.argv):
        options = cls.options(argv)

        reactor = options["reactor"]
        service = cls.service(
            plugin=options.plugins[options.subCommand],
            options=options.subOptions,
        )

        cls.startService(reactor, service)
        cls.run(cls.runnerOptions(options))



if __name__ == "__main__":
    Twist.main()
