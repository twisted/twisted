# -*- coding: Latin-1 -*-

"""
This is a compatibility hack to turn twisted.python.log functions into calls
to the new logging module in 2.3.
"""

import sys
import logging
import logging.handlers

from twisted.python import log

class Unfilter(logging.Filter):
    def filter(self, record):
        return 1

class LogOwner:
    fmt = "%(asctime)s [%(name)s] %(message)s"

    preBufferSize = 1024 * 1024 # 1 meg in memory, then bye-bye!  Better start
                                # logging before then.

    def __init__(self):
        self.formatter = logging.Formatter(self.fmt)
        self.filer = logging.handlers.MemoryHandler(self.preBufferSize)
        self.filer.setFormatter(self.formatter)
        self.filer.addFilter(Unfilter())
        self.logs = []
        self._log = logging.getLogger("Uninitialized")
        self._log.addHandler(self.filer)
        self._log.setLevel(1)

    
    def replaceFiler(self, filer):
        self._log.removeHandler(self.filer)
        for l in self.logs:
            l.removeHandler(self.filer)

        try:
            self.filer.setTarget(filer)
        except:
            pass
        else:
            self.filer.flush()

        self.filer = filer
        self.filer.setFormatter(self.formatter)
        self.filer.addFilter(Unfilter())
        self._log.addHandler(self.filer)
        for l in self.logs:
            l.addHandler(self.filer)

    def own(self, owner):
        if owner is not None:
            log = logging.getLogger(owner.logPrefix())
            log.addHandler(self.filer)
            log.setLevel(1)
            self.logs.append(log)
    
    def disown(self, owner):
        if self.logs:
            del self.logs[-1]
        else:
            self._log.error("Bad disown: %r, owner stack is empty" % (owner,))
    
    def owner(self):
        try:
            return self.logs[-1]
        except:
            return self._log

def msg(*args):
    logOwner.owner().info(' '.join(map(str, args)))

def err(*args):
    logOwner.owner().error(' '.join(map(str, args)))

class LogWrapper:
    softspace = None
    
    def __init__(self, f):
        self.f = f
        self.buffer = []

    def write(self, s):
        self.buffer.append(s)
        if self.buffer[-1].endswith('\n'):
            s = ''.join(self.buffer).rstrip()
            del self.buffer[:]
            self.f(s)

    def flush(self):
        logOwner.filer.flush()

def startLogging(logFile, setStdout=1):
    """Initialize logging to a specified file."""
    print 'Logging to', logFile
    logOwner.replaceFiler(logging.StreamHandler(logFile))
    msg("Log opened.")
    if setStdout:
        sys.stdout = LogWrapper(msg)
#        sys.stderr = LogWrapper(err)

from twisted.python import log

log.msg = msg
log.err = err
log.startLogging = startLogging
logOwner = log.logOwner = LogOwner()
