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
    f = server.DNSServerFactory(
        clients=[client.Resolver(resolv='/etc/resolv.conf')],
    )

    p = dns.DNSDatagramProtocol(controller=f)

    reactor.listenUDP(10053, p)
    reactor.listenTCP(10053, f)

    reactor.run()


if __name__ == '__main__':
    raise SystemExit(main())
