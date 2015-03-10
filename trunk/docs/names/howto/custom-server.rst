:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Creating a custom server
========================
The builtin DNS server plugin is useful,
but the beauty of Twisted Names is that you can build your own custom servers and clients using the names components.

 - In this section you will learn about the components required to build a simple DNS server.
 - You will then learn how to create a custom DNS server which calculates responses dynamically.

A simple forwarding DNS server
------------------------------
Lets start by creating a simple forwarding DNS server, which forwards all requests to an upstream server (or servers).

:download:`simple_server.py <listings/names/simple_server.py>`

.. literalinclude:: listings/names/simple_server.py

In this example we are passing a :api:`twisted.names.client.Resolver <client.Resolver>` instance
to the :api:`twisted.names.server.DNSServerFactory <DNSServerFactory>`
and we are configuring that client to use the upstream DNS servers which are specified in a local ``resolv.conf`` file.

Also note that we start the server listening on both UDP and TCP ports.
This is a standard requirement for DNS servers.

You can test the server using ``dig``.
For example:

.. code-block:: console

    $ dig -p 10053 @127.0.0.1 example.com SOA +short
    sns.dns.icann.org. noc.dns.icann.org. 2013102791 7200 3600 1209600 3600

A server which computes responses dynamically
---------------------------------------------
Now suppose we want to create a bespoke DNS server which responds to certain hostname queries
by dynamically calculating the resulting IP address, while passing all other queries to another DNS server.
Queries for hostnames matching the pattern **workstation{0-9}+**
will result in an IP address where the last octet matches the workstation number.

We'll write a custom resolver which we insert before the standard client resolver.
The custom resolver will be queried first.

Here's the code:

:download:`override_server.py <listings/names/override_server.py>`

.. literalinclude:: listings/names/override_server.py

Notice that ``DynamicResolver.query`` returns a :api:`twisted.internet.defer.Deferred <Deferred>`.
On success, it returns three lists of DNS records (answers, authority, additional),
which will be encoded by :api:`twisted.names.dns.Message <dns.Message>` and returned to the client.
On failure, it returns a :api:`twisted.names.error.DomainError <DomainError>`,
which is a signal that the query should be dispatched to the next client resolver in the list.

.. note::
   The fallback behaviour is actually handled by :api:`twisted.names.resolve.ResolverChain <ResolverChain>`.

   ResolverChain is a proxy for other resolvers.
   It takes a list of :api:`twisted.internet.interfaces.IResolver <IResolver>` providers
   and queries each one in turn until it receives an answer, or until the list is exhausted.

   Each :api:`twisted.internet.interfaces.IResolver <IResolver>` in the chain may return a deferred :api:`twisted.names.error.DomainError <DomainError>`,
   which is a signal that :api:`twisted.names.resolve.ResolverChain <ResolverChain>` should query the next chained resolver.

   The :api:`twisted.names.server.DNSServerFactory <DNSServerFactory>` constructor takes a list of authoritative resolvers, caches and client resolvers
   and ensures that they are added to the :api:`twisted.names.resolve.ResolverChain <ResolverChain>` in the correct order.

Let's use ``dig`` to see how this server responds to requests that match the pattern we specified:

.. code-block:: console

    $ dig -p 10053 @127.0.0.1 workstation1.example.com A +short
    172.0.2.1

    $ dig -p 10053 @127.0.0.1 workstation100.example.com A +short
    172.0.2.100

And if we issue a request that doesn't match the pattern:

.. code-block:: console

    $ dig -p 10053 @localhost www.example.com A +short
    93.184.216.119

Further Reading
---------------
For simplicity, the examples above use the ``reactor.listenXXX`` APIs.
But your application will be more flexible if you use the :doc:`Twisted Application APIs <../../core/howto/application>`,
along with the :doc:`Twisted plugin system <../../core/howto/plugin>` and ``twistd``.
Read the source code of :api:`twisted.names.tap <names.tap>` to see how the ``twistd names`` plugin works.
