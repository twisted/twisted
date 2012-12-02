from twisted.internet import task, defer
from twisted.internet.endpoints import connectProtocol, TCP4ClientEndpoint
from twisted.protocols import amp
from ampserver import Sum, Divide


def doMath(reactor):
    destination = TCP4ClientEndpoint(reactor, '127.0.0.1', 1234)

    d1 = connectProtocol(destination, amp.AMP()).addCallback(
        lambda p: p.callRemote(Sum, a=13, b=81)).addCallback(
        lambda result: result['total'])

    def trapZero(result):
        result.trap(ZeroDivisionError)
        print "Divided by zero: returning INF"
        return 1e1000
    d2 = connectProtocol(destination, amp.AMP()).addCallback(
            lambda p: p.callRemote(Divide, numerator=1234,
                                   denominator=0)).addErrback(trapZero)

    def done(result):
        print 'Done with math:', result
    return defer.DeferredList([d1, d2]).addCallback(done)


if __name__ == '__main__':
    task.react(doMath, [])

