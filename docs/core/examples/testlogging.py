# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Test logging.

Message should only be printed second time around.
"""


import sys
import warnings

from twisted.internet import reactor
from twisted.python import log


def test(i):
    print("printed", i)
    log.msg(f"message {i}")
    warnings.warn(f"warning {i}")
    try:
        raise RuntimeError(f"error {i}")
    except BaseException:
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
