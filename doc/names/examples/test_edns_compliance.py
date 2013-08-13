# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example trial test module which demonstrates how the low level
L{dns._OPTHeader} class can be used for testing DNS servers for
compliance with DNS RFCs.

This example should be run using trial eg

 trial doc/names/examples/test_edns_compliance.py

 OR

 TARGET=127.0.0.1 trial doc/names/examples/test_edns_compliance.py
"""

import os

from twisted.internet import reactor
from twisted.names import dns, edns
from twisted.trial import unittest



class DNSMessageManglingProtocol(dns.DNSDatagramProtocol):
    """
    A L{dns.DNSDatagramProtocol} subclass with hooks for mangling a
    L{dns.Message} before it is sent.
    """

    def __init__(self, *args, **kwargs):
        """
        @param mangler: A callable which will be passed a message
            argument and must return a message which will then be
            encoded and sent.
        @type mangler: L{callable}

        @see: L{dns.DNSDatagramProtocol.__init__} for inherited
            arguments.
        """
        self.mangler = kwargs.pop('mangler')
        dns.DNSDatagramProtocol.__init__(self, *args, **kwargs)


    def writeMessage(self, message, address):
        """
        Send a message holding DNS queries.

        @type message: L{dns.Message}
        """
        message = self.mangler(message)
        return dns.DNSDatagramProtocol.writeMessage(self, message, address)



def serversUnderTest(default):
    """
    Return a list of server information tuples found in the
    environment or C{default} if none are found.

    @param default: A default list of servers to be tested if none
        were found among the environment variables.
    @type default: L{list} of 3-L{tuple}.

    @return: L{list} of L{tuple} containing target server info
        (host, port, description)
    """
    targetServer = os.environ.get('TARGET')
    if targetServer is not None:
        parts = targetServer.split(',', 2)
        if len(parts) == 2:
            parts.append(parts[0])
        if len(parts) == 1:
            parts.extend([53, parts[0]])
        parts[1] = int(parts[1])
        return [tuple(parts)]
    else:
        return default



# Default servers to be tested
SERVERS = [
    # GoogleDNS public recursive resolver
    ('8.8.8.8', 53, 'GoogleRecursiveDns'),

    # OpenDNS public recursive resolver
    ('208.67.222.222', 53, 'OpenDNS'),

    # Twisted 13.1 Authoritative DNS (ns1.twistedmatrix.com)
    ('66.35.39.66', 53, 'TwistedAuthoritativeDns'),

    # Bind 9.9.3-S1-P1 (as reported by version.bind CH TXT) (ams.sns-pb.isc.org)
    ('199.6.1.30', 53, 'Bind9.9'),

    # Power DNS (as reported by version.bind CH TXT) (dns-us1.powerdns.net)
    ('46.165.192.30', 53, 'PowerDNS'),

    # NSD 4.0.0b5 (as reported by version.bind CH TXT) (open.nlnetlabs.nl)
    ('213.154.224.1', 53, 'NSD4'),

    # DJBDNS (uz5dz39x8xk8wyq3dzn7vpt670qmvzx0zd9zg4ldwldkv6kx9ft090.ns.yp.to.)
    # ('131.155.71.143', 53, 'DJBDNS')
]



class DNSComplianceTestBuilder(object):
    """
    Build a dictionary of L{unittest.TestCase} classes each of which
    runs a group of tests against a particular server.
    """
    @classmethod
    def makeTestCaseClasses(cls):
        """
        Create a L{unittest.TestCase} subclass which mixes in C{cls}
        for each server and return a dict mapping their names to them.
        """
        classes = {}
        for host, port, description in serversUnderTest(SERVERS):
            name = (cls.__name__ + "." + description).replace(".", "_")
            class testcase(cls, unittest.TestCase):
                __module__ = cls.__module__
                server = (host, port)
            testcase.__name__ = name
            classes[testcase.__name__] = testcase
        return classes



def hasAdditionalOptRecord(message):
    """
    Test a message for an L{dns._OPTHeader} instance among its
    additional records.
    """
    for r in message.additional:
        if r.type == dns.OPT:
            return True
    return False



class RFC6891Tests(DNSComplianceTestBuilder):
    """
    Tests for compliance with RFC6891.

    https://tools.ietf.org/html/rfc6891#section-6.1.1
    """
    def connectProtocol(self, proto):
        """
        Connect C{proto} to a listening UDP port and add a cleanup to
        stop the port when the current test finishes.

        @param proto: A L{twisted.internet.protocols.DatagramProtocol}
            instance.
        """
        port = reactor.listenUDP(0, proto)
        self.addCleanup(port.stopListening)


    def test_611_ednsResponseToEdnsRequest(self):
        """
        If an OPT record is present in a received request, compliant
        responders MUST include an OPT record in their respective
        responses.

        https://tools.ietf.org/html/rfc6891#section-6.1.1
        """

        def addOptRecord(message):
            message.additional.append(dns._OPTHeader(version=1))
            return message

        proto = DNSMessageManglingProtocol(
            controller=None, mangler=addOptRecord)
        self.connectProtocol(proto)

        d = proto.query(self.server, [dns.Query('.', dns.NS, dns.IN)])

        def checkForOpt(message):
            self.assertTrue(
                hasAdditionalOptRecord(message),
                'Message did not contain an OPT record '
                + 'in its additional section. '
                + 'rCode: %s, ' % (message.rCode,)
                + 'answers: %s, ' % (message.answers,)
                + 'authority: %s, ' % (message.authority,)
                + 'additional: %s ' % (message.additional,))
        d.addCallback(checkForOpt)

        return d


    def test_611_formErrOnMultipleOptRecords(self):
        """
        When an OPT RR is included within any DNS message, it MUST be
        the only OPT RR in that message.  If a query message with more
        than one OPT RR is received, a FORMERR (RCODE=1) MUST be
        returned.

        https://tools.ietf.org/html/rfc6891#section-6.1.1
        """
        def addMultipleOptRecord(message):
            message.additional.extend([dns._OPTHeader(), dns._OPTHeader()])
            return message

        proto = DNSMessageManglingProtocol(
            controller=None, mangler=addMultipleOptRecord)
        self.connectProtocol(proto)

        d = proto.query(self.server, [dns.Query('.', dns.NS, dns.IN)])

        d.addCallback(
            lambda message: self.assertEqual(message.rCode, dns.EFORMAT))

        return d


    def test_613_badVersion(self):
        """
        If a responder does not implement the VERSION level of the
        request, then it MUST respond with RCODE=BADVERS.

        https://tools.ietf.org/html/rfc6891#section-6.1.3
        """
        proto = edns.EDNSDatagramProtocol(
            controller=None, ednsVersion=255)

        self.connectProtocol(proto)

        d = proto.query(self.server, [dns.Query('.', dns.NS, dns.IN)])

        d.addCallback(
            lambda message: self.assertEqual(message.rCode, dns.EBADVERSION))

        return d


    def test_7_nonEdnsResponseToNonEdnsRequest(self):
        """
        Lack of presence of an OPT record in a request MUST be taken as an
        indication that the requestor does not implement any part of this
        specification and that the responder MUST NOT include an OPT record
        in its response.

        https://tools.ietf.org/html/rfc6891#section-7
        """

        proto = dns.DNSDatagramProtocol(controller=None)
        self.connectProtocol(proto)

        d = proto.query(self.server, [dns.Query('.', dns.NS, dns.IN)])

        def checkForOpt(message):
            self.assertFalse(
                hasAdditionalOptRecord(message),
                'Message contained an OPT record '
                + 'in its additional section. '
                + 'rCode: %s, ' % (message.rCode,)
                + 'answers: %s, ' % (message.answers,)
                + 'authority: %s, ' % (message.authority,)
                + 'additional: %s ' % (message.additional,))
        d.addCallback(checkForOpt)

        return d



globals().update(
    RFC6891Tests.makeTestCaseClasses())
