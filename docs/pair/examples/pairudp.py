# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is an example of using Twisted Pair's Linux tun/tap integration to receive
and react to ethernet, ip, and udp datagrams as if the example process were a
network device reachable via a system network interface.

Some system setup is required to successfully run this example.  As a
privileged user (in other words, root), these commands will create the
necessary tap network interface:

$ ip tuntap add dev tap0 mode tap user ${USER_ID}
$ ip link set dev tap0 up
$ ip neigh add ${IP_ADDRESS} lladdr ${MAC_ADDRESS} dev tap0
$ ip route add to ${IP_NETWORK} dev tap0

Once you've done this, sending UDP datagrams to ${IP_ADDRESS} on port 42 will
trigger a response from this example.

Use the UID of the user you want to be able to run the example for ${USER_ID}
and use something like 10.0.0.0/24 for ${IP_NETWORK}.

Invent any valid value for ${MAC_ADDRESS} (though avoid re-using an address
already in use on your network).

See the Twisted Pair configuration howto for more information about this
system-level setup.

When the tap device is configured, the example is running, and a UDP datagram
is sent to the right address, the example will display information about the
datagram on its standard out.
"""

from __future__ import print_function

from sys import stdout

from twisted.internet import protocol
from twisted.internet.task import react
from twisted.internet.defer import Deferred
from twisted.pair.ethernet import EthernetProtocol
from twisted.pair.ip import IPProtocol
from twisted.pair.rawudp import RawUDPProtocol
from twisted.pair.tuntap import TuntapPort
from twisted.python.log import startLogging



class MyProto(protocol.DatagramProtocol):
    def datagramReceived(self, datagram, address):
        print('from', address, 'received', repr(datagram))



def main(reactor):
    startLogging(stdout, setStdout=False)
    udp = RawUDPProtocol()
    udp.addProto(42, MyProto())
    ip = IPProtocol()
    ip.addProto(17, udp)
    eth = EthernetProtocol()
    eth.addProto(0x800, ip)

    port = TuntapPort(interface='tap0', proto=eth, reactor=reactor)
    port.startListening()

    # Run forever
    return Deferred()


if __name__ == '__main__':
    react(main, [])
