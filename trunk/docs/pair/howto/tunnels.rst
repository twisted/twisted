
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Twisted Pair: Tunnels And Network Taps
======================================
On Linux, Twisted Pair supports the special *tun* and *tap* network interface types.
This functionality allows you to interact with raw sockets (for example, to send or receive ICMP or ARP traffic).
It also allows the creation of simulated networks.
This document will not cover the details of these platform-provided features, but it will explain how to use the Twisted Pair APIs which interact with them.
Before reading this document, you may want to familiarize yourself with Linux tuntap if you have not already done so
(good online resources, are a little scarce, but you may find the `linux tuntap tutorial <https://www.google.com/search?q=linux+tuntap+tutorial>`_ google results helpful).

Tuntap Ports
------------
The :api:`twisted.pair.tuntap.TuntapPort <twisted.pair.tuntap.TuntapPort>` class is the entry point into the tun/tap functionality.
This class is initialized with an application-supplied protocol object and associates that object with a tun or tap device on the system.
If the protocol provides :api:`twisted.pair.ethernet.IEthernetProtocol <twisted.pair.ethernet.IEthernetProtocol>` then it is associated with a tap device.
Otherwise the protocol must provide :api:`twisted.pair.raw.IRawPacketProtocol <twisted.pair.raw.IRawPacketProtocol>` and it will be associated with a tun device.

.. code-block:: python

    from zope.interface import implementer
    from twisted.pair.tuntap import TuntapPort
    from twisted.pair.ethernet import EthernetProtocol
    from twisted.pair.rawudp import RawUDPProtocol
    from twisted.internet import reactor

    # Note that you must run this example as a user with permission to open this
    # device.  That means run it as root or pre-configure tap0 and assign ownership
    # of it to a non-root user.  The same goes for tun0 below.

    tap = TuntapPort(b"tap0", EthernetProtocol(), reactor=reactor)
    tap.startListening()

    tun = TuntapPort(b"tun0", RawUDPProtocol(), reactor=reactor)
    tun.startListening()

In the above example two protocols are attached to the network: one to a tap device and the other to a tun device.
The ``EthernetProtocol`` used in this example is a very simple implementation of ``IEthernetProtocol`` which does nothing more than dispatch to some other protocol based on the protocol found in the header of each ethernet frame it receives. ``RawUDPProtocol`` is similar - it dispatches to other protocols based on the UDP port of IP datagrams it received.
This example won't do anything since no application protocols have been added to either the ``EthernetProtocol`` or ``RawUDPProtocol`` instances
(not to mention the reactor isn't being started).
However, it should give you some idea of how tun/tap functionality fits into a Twisted application.

By the behaviors of these two protocols you can see the primary difference between tap and tun devices.
The lower level of the two, tap devices, is hooked in to the network stack at the ethernet layer.
When a ``TuntapPort`` is associated with a tap device, it delivers whole ethernet frames to its protocol.
The higher level version, tun devices, strips off the ethernet layer before delivering data to the application.
This means that a ``TuntapPort`` associated with a tun device most commonly delivers IP datagrams to its protocol (though if your network is being used to convey non-IP datagrams then it may deliver those instead).

Both ``IEthernetProtocol`` and ``IRawSocketProtocol`` are similar to :api:`twisted.internet.protocol.DatagramProtocol <twisted.internet.protocol.DatagramProtocol>` .
Datagrams, either ethernet or otherwise, are delivered to the protocol's ``datagramReceived`` method.
Conversely the protocol is associated with a transport with a ``write`` method that accepts datagrams for injection into the network.

You can see an example of some of this functionality in the :download:`../examples/pairudp.py` example.
