# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
C{twist} command line tool.
"""

import sys

from twisted.python.usage import UsageError
from twisted.logger import Logger
from ..runner import Runner, RunnerOptions, exit, ExitStatus
from ._options import TwistOptions



class Twist(object):
    """
    C{twist} command line tool.
    """

    log = Logger()


    @classmethod
    def main(cls, argv=sys.argv):
        twistOptions = TwistOptions()

        try:
            twistOptions.parseOptions(argv[1:])
        except UsageError as e:
            exit(ExitStatus.EX_USAGE, "Error: {}\n\n{}".format(e, twistOptions))

        runnerOptions = {
            RunnerOptions.reactor: twistOptions["reactor"],
        }

        ################# START DELETE THIS #################

        def whenRunning(options):
            from twisted.internet import reactor

            cls.log.info(
                "Reactor is running: {reactor}",
                reactor=reactor,
            )

            try:
                cls.log.info(
                    "PID file: {fp.path}",
                    fp=options[RunnerOptions.pidFilePath],
                )
            except KeyError:
                pass

            def stop():
                cls.log.info("Stopping reactor...")
                reactor.stop()

            reactor.callLater(4.0, stop)

            cls.log.info("Waiting...")

        ################# END DELETE THIS #################

        runnerOptions = {
            RunnerOptions.reactor: twistOptions["reactor"],

            RunnerOptions.logFile: sys.stdout,
            RunnerOptions.whenRunning: whenRunning,
        }

        pidFilePath = twistOptions.get("pidFilePath")
        if pidFilePath is not None:
            runnerOptions[RunnerOptions.pidFilePath] = pidFilePath

        # RunnerOptions.kill
        # RunnerOptions.defaultLogLevel
        # RunnerOptions.logFile
        # RunnerOptions.fileLogObserverFactory
        # RunnerOptions.whenRunning
        # RunnerOptions.reactorExited

        runner = Runner(runnerOptions)

        runner.run()



if __name__ == "__main__":
    Twist.main()
