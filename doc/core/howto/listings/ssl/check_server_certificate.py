#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to enable verification of a server
certificate.  It also shows how the certificate can be accessed from a
connected protocol.

If an SSL connection is successfully established, the server
certificate will be printed to stdout.

If the --verify option is used, the server certificate will be checked
for a valid signature from one of the trusted certificate authorities
provided by the operating system. eg

 python check_server_certificate.py --verify imap.gmail.com 993

 OR

 python check_server_certificate.py -v -t ./server.pem localhost 8000

"""

import sys

from twisted.internet import defer, endpoints, protocol, ssl, task
from twisted.python import usage



def connectProtocol(endpoint, proto):
    """
    XXX: delete after merging forward.
    """
    class OneShotFactory(protocol.Factory):
        def buildProtocol(self, addr):
            return proto
    return endpoint.connect(OneShotFactory())



class DelayedDisconnectProtocol(protocol.Protocol):
    """
    A protocol which schedules its disconnection and fires a deferred
    on connectionLost.

    Used to allow enough time for the SSL handshake to be completed
    before disconnecting and examining the certificate supplied by the
    server.
    """
    def __init__(self, reactor, delay):
        self._reactor = reactor
        self._delay = delay
        self.onConnectionLost = defer.Deferred()

    def connectionMade(self):
        self._reactor.callLater(self._delay, self.transport.loseConnection)

    def connectionLost(self, reason):
        self.onConnectionLost.callback((self, reason))



def printCertificate((proto, reason)):
    """
    If the SSL handshake comleted successfully, the server certificate
    can be accessed using the C{getPeerCertificate} of the underlying
    SSL transport.

    The certificate returned by C{getPeerCertificate} is a raw OpenSSL
    x509 certificate. We wrap it in a more user friendly
    L{twisted.internet.ssl.Certficate}.

    If the SSL handshake fails, an SSL specific error will be supplied
    to C{connectionLost} on the protocol.
    """
    x509 = proto.transport.getPeerCertificate()
    if x509 is not None:
        cert = ssl.Certificate(x509)
        print cert.dumpPEM()
        print "SERVER CERTIFICATE:", cert

    if reason.check(ssl.SSL.Error):
        print "SSL CONNECT ERROR:", reason.value



class Options(usage.Options):
    """
    Allow certificate verification to be turned on or off from the
    command line.
    """
    synopsis = 'Usage: check_server_certificate.py HOST PORT'

    optFlags = [
        ["verify", "v", "Verify that the server is using a trusted certificate."],
    ]

    def opt_trusted_certificate(self, certificatePath):
        """
        Specify the path to a trusted certificate or certificate authority
        file.
        Default: USE PLATFORM CERTIFICATES
        """
        # Parse a PEM file using twisted.internet.ssl.Certificate.loadPEM
        cert = ssl.Certificate.loadPEM(open(certificatePath).read())
        # But the sslContext factory expects OpenSSL.SSL.x509 objects,
        # which are wrapped inside the Certificate instance..
        self.setdefault('caCerts', []).append(cert.original)

    opt_t = opt_trusted_certificate


    def parseArgs(self, host, port):
        self['host'] = host
        self['port'] = int(port)


    def postOptions(self):
        self.setdefault('caCerts', ssl.CASources.PLATFORM)



def connectAndCheckCertificate(reactor, options):
    """
    Establish an SSL connection to a given host and port.

    Perform certificate verification if chosen by the user.

    Set a delay of 0.5 seconds before disconnecting, to allow enough
    time for the SSL handshake to complete.

    Wait for the protocol to disconnect before starting the
    certificate examination.
    """
    contextFactory = ssl.CertificateOptions(
        verify=options['verify'],
        caCerts=options['caCerts']
    )

    ep = endpoints.SSL4ClientEndpoint(
        reactor, options['host'], options['port'],
        sslContextFactory=contextFactory)

    proto = DelayedDisconnectProtocol(reactor, delay=0.5)

    d = connectProtocol(ep, proto)
    d.addCallback(lambda proto: proto.onConnectionLost)
    d.addCallback(printCertificate)
    return d



def main(reactor, *argv):
    """
    Validate command line options and begin the SSL connection.
    """
    options = Options()
    try:
        options.parseOptions(argv)
    except usage.UsageError as errortext:
        sys.stderr.write(str(options) + '\n')
        sys.stderr.write('ERROR: %s\n' % (errortext,))
        raise SystemExit(1)

    return connectAndCheckCertificate(reactor, options)



task.react(main, sys.argv[1:])
