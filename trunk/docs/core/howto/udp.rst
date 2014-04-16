
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

UDP Networking
==============

Overview
--------

Unlike TCP, UDP has no notion of connections.
A UDP socket can receive datagrams from any server on the network and send datagrams to any host on the network.
In addition, datagrams may arrive in any order, never arrive at all, or be duplicated in transit.

Since there are no connections, we only use a single object, a protocol, for each UDP socket.
We then use the reactor to connect this protocol to a UDP transport, using the :api:`twisted.internet.interfaces.IReactorUDP <twisted.internet.interfaces.IReactorUDP>` reactor API.


DatagramProtocol
----------------

The class where you actually implement the protocol parsing and handling will usually be descended from :api:`twisted.internet.protocol.DatagramProtocol <twisted.internet.protocol.DatagramProtocol>` or from one of its convenience children.
The ``DatagramProtocol`` class receives datagrams and can send them out over the network.
Received datagrams include the address they were sent from.
When sending datagrams the destination address must be specified.

Here is a simple example::

    from twisted.internet.protocol import DatagramProtocol
    from twisted.internet import reactor

    class Echo(DatagramProtocol):

        def datagramReceived(self, data, (host, port)):
            print "received %r from %s:%d" % (data, host, port)
            self.transport.write(data, (host, port))

    reactor.listenUDP(9999, Echo())
    reactor.run()

As you can see, the protocol is registered with the reactor.
This means it may be persisted if it's added to an application, and thus it has :api:`twisted.internet.protocol.AbstractDatagramProtocol.startProtocol <startProtocol>` and :api:`twisted.internet.protocol.AbstractDatagramProtocol.stopProtocol <stopProtocol>` methods that will get called when the protocol is connected and disconnected from a UDP socket.

The protocol's ``transport`` attribute will implement the :api:`twisted.internet.interfaces.IUDPTransport <twisted.internet.interfaces.IUDPTransport>` interface.
Notice that the ``host`` argument should be an IP address, not a hostname.
If you only have the hostname use ``reactor.resolve()`` to resolve the address (see :api:`twisted.internet.interfaces.IReactorCore.resolve <twisted.internet.interfaces.IReactorCore.resolve>`).


Adopted Datagram Ports
----------------------

It is also possible to add an existing ``SOCK_DGRAM`` file descriptor to the reactor using the :api:`twisted.internet.interfaces.IReactorSocket.adoptDatagramPort <adoptDatagramPort>` API.

Here is a simple example:

:download:`adopt_datagram_port.py <listings/udp/adopt_datagram_port.py>`

.. literalinclude:: listings/udp/adopt_datagram_port.py

.. note::
   - You must ensure that the socket is non-blocking before passing its file descriptor to :api:`twisted.internet.interfaces.IReactorSocket. adoptDatagramPort <adoptDatagramPort>`.
   - :api:`twisted.internet.interfaces.IReactorSocket. adoptDatagramPort <adoptDatagramPort>` cannot (`currently <https://twistedmatrix.com/trac/ticket/5599>`_) detect the family of the adopted socket so you must ensure that you pass the correct socket family argument.
   - The reactor will not shutdown the socket.
     It is the responsibility of the process that created the socket to shutdown and clean up the socket when it is no longer needed.


Connected UDP
-------------

A connected UDP socket is slightly different from a standard one as it can only send and receive datagrams to/from a single address.
However this does not in any way imply a connection as datagrams may still arrive in any order and the port on the other side may have no one listening.
The benefit of the connected UDP socket is that it **may** provide notification of undelivered packages.
This depends on many factors (almost all of which are out of the control of the application) but still presents certain benefits which occasionally make it useful.

Unlike a regular UDP protocol, we do not need to specify where to send datagrams and are not told where they came from since they can only come from the address to which the socket is 'connected'.

.. code-block:: python

    from twisted.internet.protocol import DatagramProtocol
    from twisted.internet import reactor

    class Helloer(DatagramProtocol):

        def startProtocol(self):
            host = "192.168.1.1"
            port = 1234

            self.transport.connect(host, port)
            print "now we can only send to host %s port %d" % (host, port)
            self.transport.write("hello") # no need for address

        def datagramReceived(self, data, (host, port)):
            print "received %r from %s:%d" % (data, host, port)

        # Possibly invoked if there is no server listening on the
        # address to which we are sending.
        def connectionRefused(self):
            print "No one listening"

    # 0 means any port, we don't care in this case
    reactor.listenUDP(0, Helloer())
    reactor.run()

Note that ``connect()``, like ``write()`` will only accept IP addresses, not unresolved hostnames.
To obtain the IP of a hostname use ``reactor.resolve()`` , e.g.::

    from twisted.internet import reactor

    def gotIP(ip):
        print "IP of 'example.com' is", ip
        reactor.callLater(3, reactor.stop)

    reactor.resolve('example.com').addCallback(gotIP)
    reactor.run()

Connecting to a new address after a previous connection or making a connected port unconnected are not currently supported, but likely will be in the future.


Multicast UDP
-------------

Multicast allows a process to contact multiple hosts with a single packet, without knowing the specific IP address of any of the hosts.
This is in contrast to normal, or unicast, UDP, where each datagram has a single IP as its destination.
Multicast datagrams are sent to special multicast group addresses (in the IPv4 range 224.0.0.0 to 239.255.255.255), along with a corresponding port.
In order to receive multicast datagrams, you must join that specific group address.
However, any UDP socket can send to multicast addresses.

:download:`MulticastServer.py <listings/udp/MulticastServer.py>`

.. literalinclude:: listings/udp/MulticastServer.py

As with UDP, with multicast there is no server/client differentiation at the protocol level.
Our server example is very simple and closely resembles a normal :api:`twisted.internet.interfaces.IReactorUDP.listenUDP <listenUDP>` protocol implementation.
The main difference is that instead of ``listenUDP``, :api:`twisted.internet.interfaces.IReactorMulticast.listenMulticast <listenMulticast>` is called with the port number.
The server calls :api:`twisted.internet.interfaces.IMulticastTransport.joinGroup <joinGroup>` to join a multicast group.
A ``DatagramProtocol`` that is listening with multicast and has joined a group can receive multicast datagrams, but also unicast datagrams sent directly to its address.
The server in the example above sends such a unicast message in reply to the multicast message it receives from the client.

:download:`MulticastClient.py <listings/udp/MulticastClient.py>`

.. literalinclude:: listings/udp/MulticastClient.py

Note that a multicast socket will have a default TTL (time to live) of 1.
That is, datagrams won't traverse more than one router hop, unless a higher TTL is set with :api:`twisted.internet.interfaces.IMulticastTransport.setTTL <setTTL>`.
Other functionality provided by the multicast transport includes :api:`twisted.internet.interfaces.IMulticastTransport.setOutgoingInterface <setOutgoingInterface>` and :api:`twisted.internet.interfaces.IMulticastTransport.setLoopbackMode <setLoopbackMode>` -- see :api:`twisted.internet.interfaces.IMulticastTransport <IMulticastTransport>` for more information.


Broadcast UDP
-------------

Broadcast allows a different way of contacting several unknown hosts.
Broadcasting via UDP sends a packet out to all hosts on the local network by sending to a magic broadcast address (``"<broadcast>"``).
This broadcast is filtered by routers by default, and there are no "groups" like multicast, only different ports.

Broadcast is enabled by passing ``True`` to :api:`twisted.internet.interfaces.IUDPTransport.setBroadcastAllowed <setBroadcastAllowed>` on the port.
Checking the broadcast status can be done with :api:`twisted.internet.interfaces.IUDPTransport.getBroadcastAllowed <getBroadcastAllowed>` on the port.

For a complete example of this feature, see :download:`udpbroadcast.py <../examples/udpbroadcast.py>`.


IPv6
----

UDP sockets can also bind to IPv6 addresses to support sending and receiving datagrams over IPv6.
By passing an IPv6 address to :api:`twisted.internet.interfaces.IReactorUDP.listenUDP <listenUDP>`'s ``interface`` argument, the reactor will start an IPv6 socket that can be used to send and receive UDP datagrams.

:download:`ipv6_listen.py <listings/udp/ipv6_listen.py>`

.. literalinclude:: listings/udp/ipv6_listen.py
