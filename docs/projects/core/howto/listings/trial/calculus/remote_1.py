# -*- test-case-name: calculus.test.test_remote_1 -*-

from twisted.protocols import basic
from twisted.internet import protocol
from calculus.base_3 import Calculation



class CalculationProxy(object):
    def __init__(self):
        self.calc = Calculation()
        for m in ['add', 'subtract', 'multiply', 'divide']:
            setattr(self, 'remote_%s' % m, getattr(self.calc, m))



class RemoteCalculationProtocol(basic.LineReceiver):
    def __init__(self):
        self.proxy = CalculationProxy()


    def lineReceived(self, line):
        op, a, b = line.split()
        a = int(a)
        b = int(b)
        op = getattr(self.proxy, 'remote_%s' % (op,))
        result = op(a, b)
        self.sendLine(str(result))



class RemoteCalculationFactory(protocol.Factory):
    protocol = RemoteCalculationProtocol



def main():
    from twisted.internet import reactor
    from twisted.python import log
    import sys
    log.startLogging(sys.stdout)
    reactor.listenTCP(0, RemoteCalculationFactory())
    reactor.run()
    

if __name__ == "__main__":
    main()
