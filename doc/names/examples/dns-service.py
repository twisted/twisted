#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Sample app to lookup SRV records in DNS.
"""

from twisted.names import client
from twisted.internet import reactor
import sys

def printAnswer((answers, auth, add)):
    if not len(answers):
        print 'No answers'
    else:
        print '\n'.join([str(x.payload) for x in answers])
    reactor.stop()

def printFailure(arg):
    print "error: could not resolve:", arg
    reactor.stop()

try:
    service, proto, domain = sys.argv[1:]
except ValueError:
    sys.stderr.write('%s: usage:\n' % sys.argv[0] +
                     '  %s SERVICE PROTO DOMAIN\n' % sys.argv[0])
    sys.exit(1)

resolver = client.Resolver('/etc/resolv.conf')
d = resolver.lookupService('_%s._%s.%s' % (service, proto, domain), [1])
d.addCallbacks(printAnswer, printFailure)

reactor.run()
