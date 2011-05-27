#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys
from twisted.python import log
from twisted.names import client
from twisted.internet import reactor


def gotResult(result):
    print result
    reactor.stop()

def gotFailure(failure):
    failure.printTraceback()
    reactor.stop()

log.startLogging(sys.stdout)
d = client.getHostByName(sys.argv[1])
d.addCallbacks(gotResult, gotFailure)

reactor.run()
