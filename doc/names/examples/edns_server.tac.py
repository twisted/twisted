# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A DNS server which replies NXDOMAIN to all queries.

Usage: twistd -noy doc/names/examples/edns_auth_server.tac.py

This server uses the protocol hacks from edns.py

The important thing is that because messages are decoded using
dns._EDNSMessage rather than dns.Message, OPT records are extracted from
the additional section of EDNS query messages during decoding.

This is one way of fixing #6645.

Additionally we force ednsVersion=None so that the server doesn't
respond with any OPT records.
Although RFC6891-7 suggests that the correct response should be FORMERR.
 * https://tools.ietf.org/html/rfc6891#section-7

Ultimately, DNSServerFactory will need modifying or replacing so that
it can dynamically respond using the correct EDNS settings and RCODE
based on the client request.

dns._EDNSMessage will also need to be made aware of RRSets so that it can
correctly limit the size of (or truncate) responses based on the
chosen maxSize.
 * https://twistedmatrix.com/trac/wiki/EDNS0#Selectivetruncate
"""

from functools import partial

from twisted.application.internet import TCPServer, UDPServer
from twisted.application.service import Application, MultiService

from twisted.names import edns, server



PORT = 10053
EDNS_VERSION = None


def makeService():
    masterService = MultiService()

    factory = server.DNSServerFactory(
        authorities=[],
        caches=[],
        clients=[])

    factory.protocol = partial(edns.EDNSStreamProtocol, ednsVersion=EDNS_VERSION)
    proto = edns.EDNSDatagramProtocol(ednsVersion=EDNS_VERSION, controller=factory)

    UDPServer(PORT, proto).setServiceParent(masterService)
    TCPServer(PORT, factory).setServiceParent(masterService)

    return masterService



application = Application("An EDNS aware noop DNS server")



makeService().setServiceParent(application)
