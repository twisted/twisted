# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import reactor, protocol
from twisted.pair import ethernet, rawudp, ip
from twisted.pair import tuntap

class MyProto(protocol.DatagramProtocol):
    def datagramReceived(self, *a, **kw):
        print a, kw

p_udp = rawudp.RawUDPProtocol()
p_udp.addProto(42, MyProto())
p_ip = ip.IPProtocol()
p_ip.addProto(17, p_udp)
p_eth = ethernet.EthernetProtocol()
p_eth.addProto(0x800, p_ip)

reactor.listenWith(tuntap.TuntapPort,
                   interface='tap0', proto=p_eth, reactor=reactor)
reactor.run()
