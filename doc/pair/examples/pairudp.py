# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from sys import stdout

from twisted.internet import reactor, protocol
from twisted.pair import ethernet, rawudp, ip, tuntap
from twisted.python.log import startLogging

startLogging(stdout, setStdout=False)

class MyProto(protocol.DatagramProtocol):
    def datagramReceived(self, *a, **kw):
        print a, kw

p_udp = rawudp.RawUDPProtocol()
p_udp.addProto(42, MyProto())
p_ip = ip.IPProtocol()
p_ip.addProto(17, p_udp)
p_eth = ethernet.EthernetProtocol()
p_eth.addProto(0x800, p_ip)

port = tuntap.TuntapPort(interface='tap%d', proto=p_eth, reactor=reactor)

# Ha ha!  It does not yet work.  Next you need to do:
# $ sudo ifconfig tap0 up
# $ sudo ip neigh add <ip address> lladdr <tap0 mac address> dev tap0
# $ sudo ip route add to <ip network> dev tap0
#
# For example, to be able to send UDP to 10.0.0.1 on port 42 (which will
# actually trigger this example to do something), use 10.0.0.1 for <ip address>
# and 10.0.0.0/24 for <ip network>

port.startListening()
reactor.run()
