from twisted.application import service, internet
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log

from sets import Set # hahaha 2.3-specific. t.p.compat should grow some primitive set support

class UDPProxyProtocol(DatagramProtocol):
    addrs = None
    def __init__(self, addrs):
        self.addrs = Set(addrs)

    def datagramReceived(self, data, (host, port)):
        if (host, port) is not in self.addrs:
            log.log("Received packet from unexpected address %s" % ((host, port),))
            return
        for i in self.addrs:
            if i != (host, port):
                self.transport.write(data, i)

def makeUDPProxy(self, addrs, ports):
    """Construct a multi-user UDPProxy
    @param addrs: sequence of length of at least 2 of (ip, port) tuples (recipients)
    @param ports: ports to listen on
    @return: a service representing the proxy
    @rtype: service.Service
    """

    if len(addrs) < 2:
        raise ValueError, "Want at least 2 addrs"
    if ports is None:
        if len(addrs) != 2:
            raise ValueError, "Can't have unspecified ports with more than 2 participants"
    else:
        if len(addrs) != len(ports):
            raise ValueError, "addrs and ports need to be same length"
    ms = service.MultiService()
    if ports is None and len(addrs) == 2:
        ports = [addrs[1][1], addrs[0][1]]
    p = UDPProxyProtocol(addrs)
    [UDPServer(port, f).setServiceParent(ms) for port in ports]
    return ms

