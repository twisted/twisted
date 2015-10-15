# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An example demonstrating how to create a custom DNS server.

The server will calculate the responses to A queries where the name begins with
the word "workstation".

Other queries will be handled by a fallback resolver.

eg
    python doc/names/howto/listings/names/override_server.py

    $ dig -p 10053 @localhost workstation1.example.com A +short
    172.0.2.1
"""

from twisted.internet import reactor, defer
from twisted.names import client, dns, error, server



class DynamicResolver(object):
    """
    A resolver which calculates the answers to certain queries based on the
    query type and name.
    """
    _pattern = 'workstation'
    _network = '172.0.2'

    def _dynamicResponseRequired(self, query):
        """
        Check the query to determine if a dynamic response is required.
        """
        if query.type == dns.A:
            labels = query.name.name.split('.')
            if labels[0].startswith(self._pattern):
                return True

        return False


    def _doDynamicResponse(self, query):
        """
        Calculate the response to a query.
        """
        name = query.name.name
        labels = name.split('.')
        parts = labels[0].split(self._pattern)
        lastOctet = int(parts[1])
        answer = dns.RRHeader(
            name=name,
            payload=dns.Record_A(address=b'%s.%s' % (self._network, lastOctet)))
        answers = [answer]
        authority = []
        additional = []
        return answers, authority, additional


    def query(self, query, timeout=None):
        """
        Check if the query should be answered dynamically, otherwise dispatch to
        the fallback resolver.
        """
        if self._dynamicResponseRequired(query):
            return defer.succeed(self._doDynamicResponse(query))
        else:
            return defer.fail(error.DomainError())



def main():
    """
    Run the server.
    """
    factory = server.DNSServerFactory(
        clients=[DynamicResolver(), client.Resolver(resolv='/etc/resolv.conf')]
    )

    protocol = dns.DNSDatagramProtocol(controller=factory)

    reactor.listenUDP(10053, protocol)
    reactor.listenTCP(10053, factory)

    reactor.run()



if __name__ == '__main__':
    raise SystemExit(main())
