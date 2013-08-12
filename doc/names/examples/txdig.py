# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A flexible tool for interrogating DNS name servers.

Example usage:
 txdig -s 8.8.8.8 example.com NS

This is a usecase for an API with the convenience of client.Resolver
while allowing fine control of the DNS query message.

I use client.Resolver.queryUDP and queryTCP instead of IResolver
methods because I want to choose the transport protocol and because
these functions return a message instance instead of just the record
sections.

I've hacked together some supporting classes in that module which
demonstrate how _EDNSMessage can be integrated with the existing
protocol and factory classes with some subclasses. More comments in
edns.py.
"""

from functools import partial
import re
import sys

from twisted.internet import task
from twisted.names import dns
from twisted.names.edns import EDNSResolver
from twisted.python import usage



ALL_QUERY_TYPES = dict(dns.QUERY_TYPES.items() + dns.EXT_QUERIES.items())



class Options(usage.Options):
    """
    Options based on dig.
    """

    synopsis = 'Usage: txdig [OPTIONS] DOMAIN_NAME QUERY_TYPE'

    optFlags = [
        ["tcp", None, "Use TCP when querying name servers."],
        ["noedns", None, "Disable EDNS."],
        ["dnssec", None, ("Requests DNSSEC records be sent "
                          "by setting the DNSSEC OK bit (DO) "
                          "in the OPT record in the additional section "
                          "of the query.")],
    ]

    optParameters = [
            ["server", "s", '127.0.0.1',
             "The name or IP address of the name server to query.", str],

            ["port", "p", 53,
             "The port number of the name server to query.", int],

            ["timeout", "t", 5,
             "The timeout for a query in seconds.", float],

            ["tries", "T", 3,
             "The number of times to try UDP queries to server.", int],

            ["edns", None, 0,
             "Specify the EDNS version to query with.", int],

            ["bufsize", None, 4096,
             "Set the UDP message buffer size advertised using EDNS0.", int],
        ]


    def parseArgs(self, queryName='', queryType='ALL_RECORDS'):
        self['queryName'] = queryName
        try:
            self['queryType'] = dns.REV_TYPES[queryType]
        except KeyError:
            raise usage.UsageError(
                'Unrecognised QUERY_TYPE %r. ' % (queryType,)
                + 'Must be one of %r' % (sorted(dns.REV_TYPES.keys()),))


    def postOptions(self):
        if self['noedns']:
            self['edns'] = None



def parseOptions():
    """
    Parse command line options and print the full usage message to
    stderr if there are errors.
    """
    options = Options()
    try:
        options.parseOptions()
    except usage.UsageError as errortext:
        sys.stderr.write(str(options) + '\n')
        sys.stderr.write('ERROR: %s\n' % (errortext,))
        raise SystemExit(1)
    return options



def formatRecord(record):
    """
    Format a record and its payload to match the dig long form.
    """
    line = []

    if isinstance(record, dns.Query):
        line.append(';')

    line.append(record.name.name.ljust(25))

    if isinstance(record, dns.RRHeader):
        line.append(str(record.ttl).ljust(6))

    line.append(
        dns.QUERY_CLASSES.get(
            record.cls, '(%s)' % (record.cls,)).ljust(5))

    line.append(
        ALL_QUERY_TYPES.get(
            record.type, '(%s)' % (record.type,)).ljust(5))

    if isinstance(record, dns.RRHeader):
        payload = str(record.payload)
        # Remove the <RECORD_NAME and > from the payload str
        line.append(payload[payload.find(' '):-1])

    # Remove the ttl from the payload, its already printed from the RRHeader.
    line = re.sub('\s+ttl=\d+', '', ' '.join(line))

    return line



def printMessage(message):
    """
    Print the sections of a message in dig long form.
    """
    sections = ("queries", "answers", "authority", "additional")
    print ";; flags:",
    for a in message.showAttributes:
        if a in sections:
            continue
        print '%s: %s,' % (a, getattr(message, a)),
    print

    for section in sections:
        records = getattr(message, section)
        print ";;", section.upper(), "SECTION:", len(records)
        for r in records:
            print formatRecord(r)
        print

    print ";; MSG SIZE recvd:", len(message.toStr())

    return message



def dig(reactor, queryName='', queryType=dns.ALL_RECORDS, queryClass=dns.IN,
        edns=0, bufsize=4096, dnssec=False,
        tcp=False, timeout=5, tries=3,
        server='127.0.0.1', port=53, **kwargs):
    """
    Query a DNS server.
    """
    r = EDNSResolver(servers=[(server, port)],
                     reactor=reactor,
                     ednsVersion=edns,
                     maxSize=bufsize,
                     dnssecOK=dnssec)

    if tcp:
        queryMethod = partial(r.queryTCP, timeout=timeout)
    else:
        queryMethod = partial(r.queryUDP, timeout=(timeout,) * tries)

    d = queryMethod(queries=[dns.Query(queryName, queryType, queryClass)])

    d.addCallback(printMessage)

    return d



def main(reactor):
    return dig(reactor, **parseOptions())



if __name__ == "__main__":
    task.react(main)
