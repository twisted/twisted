#!/usr/bin/env python

import sys
from twisted.names import client
from twisted.internet import reactor

def gotResult(result):
    print result
    reactor.stop()

def gotFailure(failure):
    failure.printTraceback()
    reactor.stop()

gethostbyname = client.theResolver.getHostByName
gethostbyname(sys.argv[1]).addCallbacks(gotResult, gotFailure)

reactor.run()
