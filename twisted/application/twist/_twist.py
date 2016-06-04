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
        service.privilegedStartService()

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
    def run(options):
        runner = Runner(options)
        runner.run()


    @classmethod
    def main(cls, argv=sys.argv):
        twistOptions = cls.options(argv)

        reactor = twistOptions["reactor"]
        service = cls.service(
            plugin=twistOptions.loadedPlugins[twistOptions.subCommand],
            options=twistOptions.subOptions,
        )

        cls.startService(reactor, service)

        cls.run(cls.runnerOptions(twistOptions))



if __name__ == "__main__":
    Twist.main()
