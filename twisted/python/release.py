"""
A release-automation toolkit.
"""

import sys, os, re

from twisted.python import failure, log, usage
from twisted.internet import protocol
from twisted.protocols import basic

debug = False

#errors

class DirectoryExists(OSError):
    """Some directory exists when it shouldn't."""
    pass

class DirectoryDoesntExist(OSError):
    """Some directory doesn't exist when it should."""
    pass

class CommandFailed(OSError):
    pass

class _TransactionFailed(OSError):
    """
    Don't raise this, it's internal.
    """

class Transaction:
    """I am a dead-simple Transaction."""

    sensitiveUndo = 0

    def run(self, data):
        try:
            return runChdirSafe(self.doIt, data)
        except:
            f = failure.Failure()

            log.msg(transaction="ERROR: %s failed."
                    % (self.__class__.__name__,),
                    failure=f)

            if self.sensitiveUndo:
                if raw_input("Are you sure you want to roll back "
                             "this transaction? ").lower().startswith('n'):
                    raise _TransactionFailed(f)
            log.msg(transaction="rolling back %s."
                    % (self.__class__.__name__,))
            try:
                runChdirSafe(self.undoIt, data, f)
            except:
                log.msg(transaction="Argh, the rollback failed.")
                import traceback
                traceback.print_exc()
            raise _TransactionFailed(f)
        

    def doIt(self, data):
        """Le's get it on!"""
        raise NotImplementedError

    def undoIt(self, data, fail):
        """Oops."""
        print "%s HAS NO ROLLBACK!" % self.__class__.__name__



def runTransactions(transactions, data):
    for trans in transactions:
        try:
            trans().run(data)
        except _TransactionFailed:
            return


def main():
    try:
        opts = Options()
        opts.parseOptions()
    except usage.UsageError, ue:
        print "%s: %s (see --help)" % (sys.argv[0], ue)
        sys.exit(2)

    runTransactions(opts['commands'])


# utilities

def sh(command):#, sensitive=0):
    """
    I'll try to execute `command', and if `sensitive' is true, I'll
    ask before running it.  If the command returns something other
    than 0, I'll raise CommandFailed(command).
    """
    if debug:# or sensitive:
        if raw_input("%r ?? " % command).startswith('n'):
            return
    log.msg(command=command)
    if os.system(command) != 0:
        raise CommandFailed(command)


def replaceInFile(filename, oldstr, newstr):
    """
    I replace the text `oldstr' with `newstr' in `filename' using sed
    and mv.
    """
    sh('cp %s %s.bak' % (filename, filename))
    f = open(filename)
    d = f.read()
    f.close()
    d = d.replace(oldstr, newstr)
    f = open(filename + '.new', 'w')
    f.write(d)
    f.close()
    sh('mv %s.new %s' % (filename, filename))


def runChdirSafe(f, *args, **kw):
    origdir = os.path.abspath('.')
    try:
        return f(*args, **kw)
    finally:
        os.chdir(origdir)


class ProcessToLog(protocol.ProcessProtocol):
    """
    A process protocol that converts process output to log
    messages. The log messages have 'process' and 'data' keys, and, if
    the output was received on stderr, an 'isError' key.
    """
    def __init__(self):
        self.outLiner = basic.LineReceiver()
        self.outLiner.lineReceived = self.outLineReceived
        self.outLiner.delimiter = '\n'

        self.errLiner = basic.LineReceiver()
        self.errLiner.lineReceived = self.errLineReceived
        self.errLiner.delimiter = '\n'
    
    def outReceived(self, data):
        self.outLiner.dataReceived(data)

    def errReceived(self, data):
        self.errLiner.dataReceived(data)

    def outLineReceived(self, line):
        log.msg(process=self, data=line)

    def errLineReceived(self, line):
        log.msg(process=self, data=line, isError=1)
