# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
C{twist} command line tool.
"""

import sys

from twisted.python.usage import UsageError
from ..service import Application, IService
from ..runner import Runner, RunnerOptions, exit, ExitStatus
from ._options import TwistOptions



class Twist(object):
    """
    C{twist} command line tool.
    """

    @classmethod
    def main(cls, argv=sys.argv):

        # Parse command line

        twistOptions = TwistOptions()

        try:
            twistOptions.parseOptions(argv[1:])
        except UsageError as e:
            exit(ExitStatus.EX_USAGE, "Error: {}\n\n{}".format(e, twistOptions))

        # Configure the runner based on the command line options

        reactor = twistOptions["reactor"]

        runnerOptions = {
            RunnerOptions.reactor: reactor,
        }

        for runnerOpt, twistOpt in (
            (RunnerOptions.defaultLogLevel, "logLevel"),
            (RunnerOptions.logFile, "logFile"),
            (RunnerOptions.fileLogObserverFactory, "fileLogObserverFactory"),
        ):
            runnerOptions[runnerOpt] = twistOptions[twistOpt]

        # Set up application service

        plugin = twistOptions.loadedPlugins[twistOptions.subCommand]
        service = plugin.makeService(twistOptions.subOptions)
        application = Application(plugin.tapname)
        service.setServiceParent(application)

        # Start the service

        IService(application).privilegedStartService()

        # Ask the reactor to stop the service before shutting down

        reactor.addSystemEventTrigger(
            "before", "shutdown", IService(application).stopService
        )

        # Instantiate and run the runner

        runner = Runner(runnerOptions)
        runner.run()



if __name__ == "__main__":
    Twist.main()
