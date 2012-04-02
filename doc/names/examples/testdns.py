#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Prints the results of an Address record lookup, Mail-Exchanger record lookup,
and Nameserver record lookup for the given hostname for a given hostname.

To run this script:
$ python testdns.py <hostname>
e.g.:
$ python testdns.py www.google.com
"""

import sys
from twisted.names import client
from twisted.internet import reactor
from twisted.names import dns

r = client.Resolver('/etc/resolv.conf')

def gotAddress(a):
    print 'Addresses: ', ', '.join(map(str, a))

def gotMails(a):
    print 'Mail Exchangers: ', ', '.join(map(str, a))

def gotNameservers(a):
    print 'Nameservers: ', ', '.join(map(str, a))

def gotError(f):
    print 'gotError'
    f.printTraceback()

    from twisted.internet import reactor
    reactor.stop()


if __name__ == '__main__':
    import sys

    r.lookupAddress(sys.argv[1]).addCallback(gotAddress).addErrback(gotError)
    r.lookupMailExchange(sys.argv[1]).addCallback(gotMails).addErrback(gotError)
    r.lookupNameservers(sys.argv[1]).addCallback(gotNameservers).addErrback(gotError)

    reactor.callLater(4, reactor.stop)
    reactor.run()
