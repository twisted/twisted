# -*- coding: Latin-1 -*-

"""
This is a compatibility hack to turn twisted.python.log functions into calls
to the new logging module in 2.3.
"""

import logging


from twisted.python import log

class LogOwner:
    def __init__(self):
        self.logs = []
        self._log = logging.getLogger("Uninitialized")

    def own(self, owner):
        if owner is not None:
            log = logging.getLogger(owner.logPrefix())
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


from twisted.python import log

log.msg = msg
log.err = err
logOwner = log.logOwner = LogOwner()
