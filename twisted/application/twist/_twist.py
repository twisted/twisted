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
        options = TwistOptions()

        try:
            options.parseOptions(argv[1:])
        except UsageError as e:
            exit(ExitStatus.EX_USAGE, "Error: {}\n\n{}".format(e, options))

        def whenRunning(options):
            from twisted.internet import reactor

            cls.log.info("Reactor is running: {}".format(reactor))
            cls.log.info("Stopping reactor...")
            reactor.stop()

        runner = Runner({
            RunnerOptions.reactor: options["reactor"],
            RunnerOptions.logFile: sys.stdout,
            RunnerOptions.whenRunning: whenRunning,
        })

        runner.run()



if __name__ == "__main__":
    Twist.main()
