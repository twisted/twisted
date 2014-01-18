# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example of a simple non-authoritative DNS server.
"""

from twisted.internet import reactor
from twisted.names import client, dns, server


def main():
    """
    Run the server.
    """
    factory = server.DNSServerFactory(
        clients=[client.Resolver(resolv='/etc/resolv.conf')]
    )

    protocol = dns.DNSDatagramProtocol(controller=factory)

    reactor.listenUDP(10053, protocol)
    reactor.listenTCP(10053, factory)

    reactor.run()


if __name__ == '__main__':
    raise SystemExit(main())
