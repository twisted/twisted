#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

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
