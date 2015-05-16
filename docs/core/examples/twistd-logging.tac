# Invoke this script with:

# $ twistd -ny twistd-logging.tac

# It will create a log file named "twistd-logging.log".  The log file will
# be formatted such that each line contains the representation of the dict
# structure of each log message.

from twisted.application.service import Application
from twisted.python.log import ILogObserver, msg
from twisted.python.util import untilConcludes
from twisted.internet.task import LoopingCall


logfile = open("twistd-logging.log", "a")


def log(eventDict):
    # untilConcludes is necessary to retry the operation when the system call
    # has been interrupted.
    untilConcludes(logfile.write, "Got a log! %r\n" % eventDict)
    untilConcludes(logfile.flush)


def logSomething():
    msg("A log message")


LoopingCall(logSomething).start(1)

application = Application("twistd-logging")
application.setComponent(ILogObserver, log)

