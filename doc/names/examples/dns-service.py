#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
USAGE: python dns-service.py SERVICE PROTO DOMAINNAME

Print the SRV records for a given DOMAINNAME eg

 python dns-service.py xmpp-client tcp gmail.com

SERVICE: the symbolic name of the desired service.

PROTO: the transport protocol of the desired service; this is usually
       either TCP or UDP.

DOMAINNAME: the domain name for which this record is valid.
"""
import sys

from twisted.names import client, error
from twisted.internet.task import react


def printResult(records, domainname):
    """
    Print the SRV records for the domainname or an error message if no
    SRV records were found.
    """
    answers, authority, additional = records
    if answers:
        sys.stdout.write(
            domainname + ' IN \n ' +
            '\n '.join(str(x.payload) for x in answers) +
            '\n')
    else:
        sys.stderr.write(
            'ERROR: No SRV records found for name %r\n' % (domainname,))


def printError(failure, domainname):
    """
    Print a friendly error message if the domainname could not be
    resolved.
    """
    failure.trap(error.DNSNameError)
    sys.stderr.write('ERROR: domain name not found %r\n' % (domainname,))


def main(reactor, *argv):
    try:
        service, proto, domainname = sys.argv[1:]
    except ValueError:
        sys.stderr.write(
            __doc__.lstrip() + '\n'
            'ERROR: incorrect command line arguments\n')
        raise SystemExit(1)

    resolver = client.Resolver('/etc/resolv.conf')
    domainname = '_%s._%s.%s' % (service, proto, domainname)
    d = resolver.lookupService(domainname)
    d.addCallback(printResult, domainname)
    d.addErrback(printError, domainname)
    return d

if __name__ == '__main__':
    react(main, sys.argv[1:])
