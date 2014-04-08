# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test logging.

Message should only be printed second time around.
"""

from twisted.python import log
from twisted.internet import reactor

import sys, warnings

def test(i):
    print "printed", i
    log.msg("message %s" % i)
    warnings.warn("warning %s" % i)
    try:
        raise RuntimeError, "error %s" % i
    except:
        log.err()

def startlog():
    log.startLogging(sys.stdout)

def end():
    reactor.stop()

# pre-reactor run
test(1)

# after reactor run
reactor.callLater(0.1, test, 2)
reactor.callLater(0.2, startlog)

# after startLogging
reactor.callLater(0.3, test, 3)
reactor.callLater(0.4, end)

reactor.run()
