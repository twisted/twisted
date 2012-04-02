#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Returns the IP address for a given hostname.
To run this script:
$ python gethostbyname.py <hostname>
e.g.:
$ python gethostbyname.py www.google.com
"""
import sys
from twisted.names import client
from twisted.internet import reactor

def gotResult(result):
    print result
    reactor.stop()

def gotFailure(failure):
    failure.printTraceback()
    reactor.stop()

d = client.getHostByName(sys.argv[1])
d.addCallbacks(gotResult, gotFailure)

reactor.run()
