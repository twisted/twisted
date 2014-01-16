:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Creating and working with a names (DNS) server
==============================================
A Names server can be perform three basic operations:

- act as a recursive server, forwarding queries to other servers
- perform local caching of recursively discovered records
- act as the authoritative server for a domain

Creating a non-authoritative server
-----------------------------------
The first two of these are easy, and you can create a server that performs them
with the command ``twistd -n dns --recursive --cache`` .
You may wish to run this as root since it will try to bind to UDP port 53.  Try
performing a lookup with it, ``dig twistedmatrix.com @127.0.0.1`` .

Creating an authoritative server
--------------------------------
To act as the authority for a domain, two things are necessary: the address
of the machine on which the domain name server will run must be registered
as a nameserver for the domain; and the domain name server must be
configured to act as the authority.  The first requirement is beyond the
scope of this howto and will not be covered.

To configure Names to act as the authority
for ``example-domain.com`` , we first create a zone file for
this domain.

:download:`example-domain.com <listings/names/example-domain.com>`

.. literalinclude:: listings/names/example-domain.com

Next, run the command ``twistd -n dns --pyzone example-domain.com`` .  Now try querying the domain locally (again, with
dig): ``dig -t any example-domain.com @127.0.0.1`` .

Names can also read a traditional, BIND-syntax zone file.  Specify these
with the ``--bindzone`` parameter.  The $GENERATE and $INCLUDE
directives are not yet supported.

Creating a custom server
------------------------
The builtin DNS server plugin is useful, but the beauty of Twisted Names is that you can build your own custom servers and clients using the names components.

A Simple Server
~~~~~~~~~~~~~~~
Lets start by creating a simple DNS server:

:download:`simple_server.py <listings/names/simple_server.py>`

.. literalinclude:: listings/names/simple_server.py

In this example, we are passing a :api:`twisted.names.client.Resolver <client.Resolver>` instance to the :api:`twisted.names.server.DNSServerFactory <DNSServerFactory>` and we are configuring that client to use the upstream DNS servers which are specified in a local resolv.conf file.

Also note that we start the server listening on both UDP and TCP ports.
This is a standard requirement for DNS servers.

You can test the server using ``dig``.
For example
::
    $ dig -p 10053 @127.0.0.1 example.com SOA +short
    sns.dns.icann.org. noc.dns.icann.org. 2013102791 7200 3600 1209600 3600

Calculate responses on the fly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Now suppose we want to create a bespoke DNS server which responds to certain hostname queries by dynamically calculating the resulting IP address, while passing all other queries to another DNS server.

ie hostname queries for names matching the pattern **workstation{0-9}+** will always result in an IP address where the last octet matches the workstation number.

We can achieve that by writing a custom resolver which we insert before the standard client resolver.
The custom resolver will be queried first, and if it returns a :api:`twisted.names.error.DomainError <DomainError>`, the :api:`twisted.names.server.DNSServerFactory <DNSServerFactory>` will then dispatch the query to the standard client.

Here's the code:
:download:`override_server.py <listings/names/override_server.py>`

.. literalinclude:: listings/names/override_server.py

In fact, the fallback behaviour is handled by :api:`twisted.names.resolve.ResolverChain <ResolverChain>`.
ResolverChain is a proxy for other resolvers.
It takes a list of :api:`twisted.internet.interfaces.IResolver <IResolver>` providers and queries each one in turn until it receives an answer.
The job of DNSServerFactory is to take a list of authoritative resolvers, caches and client resolvers and ensure that they are added to the ResolverChain in the correct order.

Let's use ``dig`` to see how this server responds to requests that match the pattern we specified.
::
    $ dig -p 10053 @127.0.0.1 workstation1.example.com A +short
    172.0.2.1

    $ dig -p 10053 @127.0.0.1 workstation100.example.com A +short
    172.0.2.100

And if we issue a request that doesn't match the pattern.
::
    $ dig -p 10053 @127.0.0.1 foobar.example.com A +short
    67.215.65.132
