from twisted.internet import reactor, defer
from twisted.internet.protocol import ClientCreator
from twisted.protocols import amp
from ampserver import Sum, Divide


def doMath():
    d1 = ClientCreator(reactor, amp.AMP).connectTCP(
        '127.0.0.1', 1234).addCallback(
            lambda p: p.callRemote(Sum, a=13, b=81)).addCallback(
                lambda result: result['total'])
    def trapZero(result):
        result.trap(ZeroDivisionError)
        print "Divided by zero: returning INF"
        return 1e1000
    d2 = ClientCreator(reactor, amp.AMP).connectTCP(
        '127.0.0.1', 1234).addCallback(
            lambda p: p.callRemote(Divide, numerator=1234,
                                   denominator=0)).addErrback(trapZero)
    def done(result):
        print 'Done with math:', result
    defer.DeferredList([d1, d2]).addCallback(done)

if __name__ == '__main__':
    doMath()
    reactor.run()
