#!/usr/bin/python

"""Sample app to lookup SRV records in DNS."""

from twisted.names import dns
from twisted.internet import main
import sys

def printAnswer(answer):
    for pri, weight, port, host in answer:
        print "pri=%d weight=%d %s:%d" % (pri, weight, host, port)
    main.shutDown()

def printFailure(arg):
    print "error: could not resolve:", arg
    main.shutDown()
    sys.exit(1)

try:
    service, proto, domain = sys.argv[1:]
except ValueError:
    sys.stderr.write('%s: usage:\n' % sys.argv[0] +
                     '  %s SERVICE PROTO DOMAIN\n' % sys.argv[0])
    sys.exit(1)

resolver = dns.ResolveConfResolver()
deferred = resolver.resolve('.'.join(('_'+service, '_'+proto, domain)),
                            type=33)
deferred.addCallback(printAnswer)
deferred.addErrback(printFailure)
deferred

main.run()
