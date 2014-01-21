:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

A Guided Tour of twisted.names.client
=====================================
Twisted Names includes multiple client APIs, at varying levels of abstraction.

In this section:

 - You will learn about the high level client API
 - You will learn about how you can use the client API interactively from the Python shell for DNS debugging and diagnostics
 - You will learn about the IResolverSimple and the IResolver interfaces,
   the implementations of those interfaces and when to use them.
 - You will learn how to customise how the reactor carries out hostname resolution
 - You will also be introduced to some of the low level interfaces


Using the Global Resolver
-------------------------
The easiest way to issue DNS queries is to use the module level functions
in :api:`twisted.names.client <names.client>`.

These will construct a global, singleton resolver object
using :api:`twisted.names.client.createResolver <createResolver>`.
That resolver is cached and used in subsequent calls to the lookup functions.

Here's an example of some DNS queries generated from an interactive Twisted shell
using :api:`twisted.conch.stdio <twisted.conch.stdio>`:


.. code-block:: console

   $ python -m twisted.conch.stdio


.. code-block:: python

   >>> from twisted.names import client
   >>> client.getHostByName('www.example.com')
   <Deferred at 0xf5c5a8 waiting on Deferred at 0xf5cb90>
   >>> _
   <Deferred at 0xf5c5a8 current result: '2606:2800:220:6d:26bf:1447:1097:aa7'>

   >>> client.lookupMailExchange('twistedmatrix.com')
   <Deferred at 0xf5cd40 waiting on Deferred at 0xf5cea8>
   >>> _
   <Deferred at 0xf5cd40 current result: ([<RR name=twistedmatrix.com type=MX class=IN ttl=1s auth=False>], [], [])>


All the ``IResolverSimple`` and ``IResolver`` methods are asynchronous and return ``deferreds``.

Notice that :api:`twisted.names.client.getHostByName <getHostByName>` (part of ``IResolverSimple``) returns an IP address.

Whereas :api:`twisted.names.client.lookupMailExchange <lookupMailExchange>` returns three lists of DNS records.

Notice also that initially the deferred returned by the DNS lookup functions has not fired
 -- it is waiting for a response from the DNS server.

We type ``_`` (the default variable) a little later,
to display its value after an answer has been received and the deferred has fired.

.. note::
   * Unlike its posix equivalent, getHostByName returns an IPv6 address

   * IResolver contains separate functions for looking up each of the common DNS record types

   * IResolver includes a lower level query function for issuing arbitrary queries.

   * The :api:`twisted.names.client <names.client>` module ``directlyProvides``
     both the :api:`twisted.internet.interfaces.IResolverSimple <IResolverSimple>`
     and the :api:`twisted.names.internet.IResolver <IResolver>` interfaces.

   * :api:`twisted.names.client.createResolver <createResolver>` constructs a global resolver
     which performs queries against the same DNS sources and servers used by the underlying operating system.

     That is, it will the DNS server IP addresses from a local ``resolv.conf`` file
     (if the operating system provides such a file)
     and it will use a OS specific hosts file path.


Creating a New Resolver
-----------------------
Now suppose we want to create a client Resolver which sends its queries to a specific server (or servers).

In this case, we use :api:`twisted.names.client.Resolver <client.Resolver>` directly
and pass it a list of preferred server IP addresses and ports.

For example, suppose we want to lookup names using the free Google DNS servers:

.. code-block:: console

   $ python -m twisted.conch.stdio

.. code-block:: python

   >>> from twisted.names import client
   >>> resolver = client.createResolver(servers=[('8.8.8.8', 53), ('8.8.4.4', 53)])
   >>> resolver.getHostByName('example.com')
   <Deferred at 0x9dcfbac current result: '93.184.216.119'>

Here we are using the Google DNS server IP addresses and the standard DNS port (53).

Installing a Resolver in the Reactor
------------------------------------
You can also install a custom resolver into the reactor
using the :api:`twisted.internet.interfaces.IReactoryPluggable <IReactorPluggable>` interface.

The reactor uses its installed resolver to resolve hostnames
that may be supplied to eg :api:`twisted.internet.interfaces.IReactoryTCP.connectTCP <connectTCP>`.

Here's a short example that shows how to install an alternative resolver for the global reactor.

.. code-block:: python

   from twisted.internet import reactor
   from twisted.names import client
   reactor.installResolver(client.createResolver(servers=[('8.8.8.8', 53), ('8.8.4.4', 53)], hosts='alternate_hosts_file'))

After this, all hostname lookups requested by the reactor will be sent to the Google DNS servers
instead of to the local operating system.

.. note::
   By default the reactor uses the posix ``gethostbyname`` function provided by the operating system.

   But ``gethostbyname`` is a blocking function, so it is called in a threadpool.

   Check out :api:`twisted.internet.base.ThreadedResolver <ThreadedResolver>`
   if you're interested in learning more about how the default threaded resolver works.
