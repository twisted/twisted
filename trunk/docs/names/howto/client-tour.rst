:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

A Guided Tour of twisted.names.client
=====================================
Twisted Names provides a layered selection of client APIs.

In this section you will learn:

* about the high level :api:`twisted.names.client <client>` API,
* about how you can use the client API interactively from the Python shell (useful for DNS debugging and diagnostics),
* about the :api:`twisted.internet.interfaces.IResolverSimple <IResolverSimple>` and the :api:`twisted.internet.interfaces.IResolver <IResolver>` interfaces,
* about various implementations of those interfaces and when to use them,
* how to customise how the reactor carries out hostname resolution,
* and finally, you will also be introduced to some of the low level APIs.


Using the Global Resolver
-------------------------
The easiest way to issue DNS queries from Twisted is to use the module level functions in :api:`twisted.names.client <names.client>`.

Here's an example showing some DNS queries generated in an interactive ``twisted.conch`` shell.

.. note::

   The ``twisted.conch`` shell starts a ``reactor`` so that asynchronous operations can be run interactively and it prints the current result of ``deferred``\ s which have fired.

   You'll notice that the ``deferred``\ s returned in the following examples do not immediately have a result -- they are waiting for a response from the DNS server.

   So we type ``_`` (the default variable) a little later, to display the value of the ``deferred`` after an answer has been received and the ``deferred`` has fired.


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


All the :api:`twisted.internet.interfaces.IResolverSimple <IResolverSimple>` and :api:`twisted.internet.interfaces.IResolver <IResolver>` methods are asynchronous and therefore return ``deferred``\ s.

:api:`twisted.names.client.getHostByName <getHostByName>` (part of :api:`twisted.internet.interfaces.IResolverSimple <IResolverSimple>`) returns an IP address whereas :api:`twisted.names.client.lookupMailExchange <lookupMailExchange>` returns three lists of DNS records.
These three lists contain answer records, authority records, and additional records.


.. note::
   * :api:`twisted.names.client.getHostByName <getHostByName>` may return an IPv6 address; unlike its stdlib equivalent (:func:`socket.gethostbyname`)

   * :api:`twisted.internet.interfaces.IResolver <IResolver>` contains separate functions for looking up each of the common DNS record types.

   * :api:`twisted.internet.interfaces.IResolver <IResolver>` includes a lower level ``query`` function for issuing arbitrary queries.

   * The :api:`twisted.names.client <names.client>` module ``directlyProvides`` both the :api:`twisted.internet.interfaces.IResolverSimple <IResolverSimple>` and the :api:`twisted.names.internet.IResolver <IResolver>` interfaces.

   * :api:`twisted.names.client.createResolver <createResolver>` constructs a global resolver which performs queries against the same DNS sources and servers used by the underlying operating system.

     That is, it will use the DNS server IP addresses found in a local ``resolv.conf`` file (if the operating system provides such a file) and it will use an OS specific ``hosts`` file path.


A simple example
~~~~~~~~~~~~~~~~

In this section you will learn how the :api:`twisted.internet.interfaces.IResolver<IResolver>` interface can be used to write a utility for performing a `reverse DNS lookup <https://en.wikipedia.org/wiki/Reverse_DNS_lookup>`_ for an IPv4 address.
`dig <https://en.wikipedia.org/wiki/Dig_(command)>`_ can do this too, so lets start by examining its output:

.. code-block:: console

   $ dig -x 127.0.0.1
   ...
   ;; QUESTION SECTION:
   ;1.0.0.127.in-addr.arpa.		IN	PTR

   ;; ANSWER SECTION:
   1.0.0.127.in-addr.arpa.	86400	IN	PTR	localhost.
   ...

As you can see, ``dig`` has performed a DNS query with the following attributes:

* Name: ``1.0.0.127.in-addr.arpa.``
* Class: ``IN``
* Type: ``PTR``

The *name* is a **reverse domain name** and is derived by reversing an IPv4 address and prepending it to the special *in-addr.arpa* parent domain name.
So, lets write a function to create a reverse domain name from an IP address.

.. literalinclude:: listings/names/reverse_lookup.py
   :pyobject: reverseNameFromIPAddress

We can test the output from a python shell:

.. code-block:: python

   >>> reverseNameFromIPAddress('192.0.2.100')
   '100.2.0.192.in-addr.arpa'

We're going to use :api:`twisted.names.client.lookupPointer` to perform the actual DNS lookup.
So lets examine the output of ``lookupPointer`` so that we can design a function to format and print its results in a style similar to ``dig``.

.. note::
   ``lookupPointer`` is an asynchronous function, so we'll use an interactive ``twisted.conch`` shell here.

.. code-block:: console

   $ python -m twisted.conch.stdio

.. code-block:: python

   >>> from twisted.names import client
   >>> from reverse_lookup import reverseNameFromIPAddress
   >>> d = client.lookupPointer(name=reverseNameFromIPAddress('127.0.0.1'))
   >>> d
   <Deferred at 0x286b170 current result: ([<RR name=1.0.0.127.in-addr.arpa type=PTR class=IN ttl=86400s auth=False>], [], [])>
   >>> d.result
   ([<RR name=1.0.0.127.in-addr.arpa type=PTR class=IN ttl=86400s auth=False>], [], [])

The deferred result of ``lookupPointer`` is a tuple containing three lists of records; **answers**, **authority**, and **additional**.
The actual record is a :api:`twisted.names.dns.Record_PTR<Record_PTR>` instance which can be reached via the :api:`twisted.names.dns.RRHeader<RRHeader>`\ ``.payload`` attribute.

.. code-block:: python

   >>> recordHeader = d.result[0][0]
   >>> recordHeader.payload
   <PTR name=localhost ttl=86400>

So, now we've found the information we need, lets create a function that extracts the first *answer* and prints the domain name and the record payload.

.. literalinclude:: listings/names/reverse_lookup.py
   :pyobject: printResult


And lets test the output:

.. code-block:: console

   >>> from twisted.names import dns
   >>> printResult(([dns.RRHeader(name='1.0.0.127.in-addr.arpa', type=dns.PTR, payload=dns.Record_PTR('localhost'))], [], []))
   1.0.0.127.in-addr.arpa IN <PTR name=localhost ttl=None>

Fine! Now we can assemble the pieces in a ``main`` function, which we'll call using :api:`twisted.internet.task.react`.
Here's the complete script.

:download:`listings/names/reverse_lookup.py <listings/names/reverse_lookup.py>`

.. literalinclude:: listings/names/reverse_lookup.py

The output looks like this:

.. code-block:: console

   $ python reverse_lookup.py 127.0.0.1
   1.0.0.127.in-addr.arpa IN <PTR name=localhost ttl=86400>

.. note::
   * You can read more about reverse domain names in :rfc:`1034#section-5.2.1`.
   * We've ignored IPv6 addresses in this example, but you can read more about reverse IPv6 domain names in :rfc:`3596#section-2.5` and the example could easily be extended to support these.
   * You might also consider using `netaddr <https://pypi.python.org/pypi/netaddr/>`_,  which can generate reverse domain names and which also includes sophisticated IP network and IP address handling.
   * This script only prints the first answer, but sometimes you'll get multiple answers due to CNAME indirection, for example in the case of classless reverse zones.
   * All lookups and responses are handled asynchronously, so the script could be extended to perform thousands of reverse DNS lookups in parallel.

Next you should study :download:`../examples/multi_reverse_lookup.py <../examples/multi_reverse_lookup.py>` which extends this example to perform both IPv4 and IPv6 addresses and which can perform multiple reverse DNS lookups in parallel.

Creating a New Resolver
-----------------------
Now suppose we want to create a DNS client which sends its queries to a specific server (or servers).

In this case, we use :api:`twisted.names.client.Resolver <client.Resolver>` directly and pass it a list of preferred server IP addresses and ports.

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
You can also install a custom resolver into the reactor using the :api:`twisted.internet.interfaces.IReactoryPluggable <IReactorPluggable>` interface.

The reactor uses its installed resolver whenever it needs to resolve hostnames; for example, when you supply a hostname to :api:`twisted.internet.interfaces.IReactoryTCP.connectTCP <connectTCP>`.

Here's a short example that shows how to install an alternative resolver for the global reactor:

.. code-block:: python

   from twisted.internet import reactor
   from twisted.names import client
   reactor.installResolver(client.createResolver(servers=[('8.8.8.8', 53), ('8.8.4.4', 53)]))

After this, all hostname lookups requested by the reactor will be sent to the Google DNS servers; instead of to the local operating system.

.. note::

   * By default the reactor uses the POSIX ``gethostbyname`` function provided by the operating system,

   * but ``gethostbyname`` is a blocking function, so it has to be called in a thread pool.

   * Check out :api:`twisted.internet.base.ThreadedResolver <ThreadedResolver>` if you're interested in learning more about how the default threaded resolver works.


Lower Level APIs
----------------

Here's an example of how to use the :api:`twisted.names.dns.DNSDatagramProtocol <DNSDatagramProtocol>` directly.

.. code-block:: python

   from twisted.internet import task
   from twisted.names import dns

   def main(reactor):
       proto = dns.DNSDatagramProtocol(controller=None)
       reactor.listenUDP(0, proto)

       d = proto.query(('8.8.8.8', 53), [dns.Query('www.example.com', dns.AAAA)])
       d.addCallback(printResult)
       return d

   def printResult(res):
       print 'ANSWERS: ', [a.payload for a in res.answers]

   task.react(main)

The disadvantage of working at this low level is that you will need to handle query failures yourself, by manually re-issuing queries or by issuing followup TCP queries using the stream based :api:`twisted.names.dns.DNSProtocol <dns.DNSProtocol>`.

These things are handled automatically by the higher level APIs in :api:`twisted.names.client <client>`.

Also notice that in this case, the deferred result of :api:`twisted.names.dns.DNSDatagramProtocol <dns.DNSDatagramProtocol.query>` is a :api:`twisted.names.dns.Message <dns.Message>` object, rather than a list of DNS records.


Further Reading
---------------
Check out the :doc:`Twisted Names Examples <../examples/index>` which demonstrate how the client APIs can be used to create useful DNS diagnostic tools.
