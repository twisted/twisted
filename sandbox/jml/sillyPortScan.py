"""Module/script that scans a single port on each computer over the network
and returns a list of all hosts that are 'up'.

- Figures out what 'local network' means based on the Windows registry
- The code is stupid tired stupid stupid, and probably duplicates stuff
- Timeout is set to one second because it's supposed to be for a local network
- zeroconf scares me
"""

from twisted.internet import protocol, reactor, defer
from bulletproof import win32goodies
import sets

bstr_pos = lambda n: n>0 and bstr_pos(n>>1)+str(n&1) or ''

def toBinary(x, count=8):
    return "".join(map(lambda y:str((x>>y)&1), range(count-1, -1, -1)))

def split(ip):
    return [int(x) for x in ip.split('.')]

def join(ip):
    return '.'.join([str(x) for x in ip ])

def binaryIP(ip):
    return ''.join(map(toBinary, ip))

def network(ip, nm):
    ip, nm = split(ip), split(nm)
    net = join([ (i & n) for i, n in zip(ip, nm) ])
    size = binaryIP(nm).rindex('1') + 1
    return net, size

def ipRange(net, size):
    masks = [ 0xFF000000L, 0x00FF0000L, 0x0000FF00L, 0x000000FFL ]
    ips = []
    for i in range((2 ** (32-size))-1):
        ip = [ (i & masks[0]) >> 24,
               (i & masks[1]) >> 16,
               (i & masks[2]) >> 8,
               (i & masks[3]) ]
        ip = join([ (n | x) for n, x in zip(split(net), ip) ])
        ips.append(ip)
    return ips



class Taster(protocol.Protocol):
    def connectionMade(self):
        self.factory.registerSuccess(self.addr.host)
        self.transport.loseConnection()

    def connectionLost(self, *args):
        self.factory.registerFailure(self.addr.host)


class TasterFactory(protocol.ClientFactory):
    protocol = Taster
    
    def clientConnectionFailed(self, connector, reason):
        self.registerFailure(connector.host)

    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        p.addr = addr
        return p

    def connect(self, ip, port):
        reactor.connectTCP(ip, port, self, timeout=1)

    def _register(self, host):
        self.done.add(host)
        
    def registerSuccess(self, host):
        self._register(host)
        self.successes.add(host)
        if self.onSuccess is not None:
            self.onSuccess(host)
        self.isScanDone()

    def registerFailure(self, host):
        self._register(host)
        self.isScanDone()

    def scan(self, ips, port, onSuccess=None):
        self.scanDeferred = defer.Deferred()
        self.numberToScan = len(ips)
        self.successes = sets.Set()
        self.done = sets.Set()
        self.onSuccess = onSuccess
        for ip in ips:
            self.connect(ip, port)
        return self.scanDeferred

    def isScanDone(self):
        if len(self.done) == self.numberToScan:
            self.scanDeferred.callback(list(self.successes))

def yes(*args):
    print('yes', args)

def scan(ips, port):
    fact = TasterFactory()
    d = fact.scan(ips, port, yes)
    d.addCallback(scanDone)
    d.addErrback(quit)

def quit(failure):
    reactor.stop()

def scanDone(successes):
    print 'all results'
    print successes
    reactor.stop()

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1])
    interfaces = win32goodies.getNetworkInterfaces()
    for gw, ip, nm in interfaces:
        net, size = network(ip, nm)
        ips = ipRange(net, size)
    scan(ips, port)
    reactor.run()
