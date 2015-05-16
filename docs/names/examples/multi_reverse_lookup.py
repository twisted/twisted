#!/usr/bin/env python
# -*- test-case-name: twisted.names.test.test_examples -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Lookup the reverse DNS pointer records for one or more IP addresses.

 python  multi_reverse_lookup.py 127.0.0.1  192.0.2.100

IPADDRESS: An IPv4 or IPv6 address.
"""
import sys
import socket

from twisted.internet import defer, task
from twisted.names import client
from twisted.python import usage



class Options(usage.Options):
    synopsis = 'Usage: multi_reverse_lookup.py IPADDRESS [IPADDRESS]'

    def parseArgs(self, *addresses):
        self['addresses'] = addresses



def reverseNameFromIPv4Address(address):
    """
    Return a reverse domain name for the given IPv4 address.
    """
    tokens = list(reversed(address.split('.'))) + ['in-addr', 'arpa', '']
    return '.'.join(tokens)



def reverseNameFromIPv6Address(address):
    """
    Return a reverse domain name for the given IPv6 address.
    """
    # Expand addresses that are in compressed format eg ::1
    fullHex = ''.join('%02x' % (ord(c),)
                      for c in socket.inet_pton(socket.AF_INET6, address))
    tokens = list(reversed(fullHex)) + ['ip6', 'arpa', '']
    return '.'.join(tokens)



def reverseNameFromIPAddress(address):
    """
    Return a reverse domain name for the given IP address.
    """
    try:
        socket.inet_pton(socket.AF_INET, address)
    except socket.error:
        return reverseNameFromIPv6Address(address)
    else:
        return reverseNameFromIPv4Address(address)



def printResult(result):
    """
    Print a comma separated list of reverse domain names and associated pointer
    records.
    """
    answers, authority, additional = result
    if answers:
        sys.stdout.write(
            ', '.join(
                '{} IN {}'.format(a.name.name, a.payload) for a in answers)
            + '\n')



def printSummary(results):
    """
    Print a summary showing the total number of responses and queries.
    """
    statuses = zip(*results)[0]
    sys.stdout.write(
        '{} responses to {} queries'.format(
            statuses.count(True), len(statuses)) + '\n')



def main(reactor, *argv):
    options = Options()
    try:
        options.parseOptions(argv)
    except usage.UsageError as errortext:
        sys.stderr.write(str(options) + '\n')
        sys.stderr.write('ERROR: %s\n' % (errortext,))
        raise SystemExit(1)

    pending = []
    for address in options['addresses']:
        pointerName = reverseNameFromIPAddress(address)
        # Force a single 1s timeout, so that slow or offline servers don't
        # adversely slow down the script.
        result = client.lookupPointer(pointerName, timeout=(1,))
        result.addCallback(printResult)
        pending.append(result)

    allResults = defer.DeferredList(pending, consumeErrors=False)
    allResults.addCallback(printSummary)
    return allResults



if __name__ == "__main__":
    task.react(main, sys.argv[1:])
