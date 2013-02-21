#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Usage: gethostbyname.py HOSTNAME

Print the IP address for a given hostname. eg

 python gethostbyname.py www.google.com

This script does a host lookup using the default Twisted Names
resolver, a chained resolver, which attempts to lookup a name from:
 * local hosts file
 * memory cache of previous lookup results
 * system recursive DNS servers
"""
import sys

from twisted.names import client, error
from twisted.internet.task import react
from twisted.python import usage


def printResult(address, hostname):
    """
    Print the IP address or an error message if an IP address was not
    found.
    """
    if address:
        sys.stdout.write(address + '\n')
    else:
        sys.stderr.write(
            'ERROR: No IP adresses found for name %r\n' % (hostname,))


def printError(failure, hostname):
    """
    Print a friendly error message if the hostname could not be
    resolved.
    """
    failure.trap(error.DNSNameError)
    sys.stderr.write('ERROR: hostname not found %r\n' % (hostname,))


class Options(usage.Options):
    synopsis = __doc__.strip()
    longdesc = ''

    def parseArgs(self, hostname):
        self['hostname'] = hostname


def main(reactor, *argv):
    options = Options()
    try:
        options.parseOptions(argv)
    except usage.UsageError as errortext:
        sys.stderr.write(
            __doc__.lstrip() + '\n')
        sys.stderr.write('ERROR: %s\n' % (errortext,))
        raise SystemExit(1)

    hostname = options['hostname']
    d = client.getHostByName(hostname)
    d.addCallback(printResult, hostname)
    d.addErrback(printError, hostname)
    return d

if __name__ == '__main__':
    react(main, sys.argv[1:])
