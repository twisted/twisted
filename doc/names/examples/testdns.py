#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Prints the results of an Address record lookup, Mail-Exchanger record
lookup, and Nameserver record lookup for the given hostname for a
given hostname.

To run this script:
$ python testdns.py <hostname>
e.g.:
$ python testdns.py www.google.com
"""
import sys

from twisted.names import client
from twisted.internet import defer, reactor
from twisted.names import dns, error


r = client.Resolver('/etc/resolv.conf')


def formatResult(a, heading):
    answer, authority, additional = a
    lines = ['# ' + heading]
    for a in answer:
        line = [
            a.name,
            dns.QUERY_CLASSES.get(a.cls, 'UNKNOWN (%d)' % (a.cls,)),
            a.payload]
        lines.append(' '.join(str(word) for word in line))

    return '\n'.join(line for line in lines)


def printError(f):
    f.trap(defer.FirstError)
    f = f.value.subFailure
    f.trap(error.DomainError)
    print f.value.__class__.__name__, f.value.message.queries


def printResults(res):
    for r in res:
        print r
        print


if __name__ == '__main__':
    domainname = sys.argv[1]

    d = defer.gatherResults([
            r.lookupAddress(domainname).addCallback(
                formatResult, 'Addresses'),
            r.lookupMailExchange(domainname).addCallback(
                formatResult, 'Mail Exchangers'),
            r.lookupNameservers(domainname).addCallback(
                formatResult, 'Nameservers'),
            ], consumeErrors=True)

    d.addCallbacks(printResults, printError)

    d.addBoth(lambda ign: reactor.stop())

    reactor.run()
