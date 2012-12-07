from twisted.internet import reactor, defer
from twisted.internet.protocol import ClientCreator
from twisted.protocols import amp
from ampserver import Sum, Divide


def doMath():
    creator = ClientCreator(reactor, amp.AMP)
    sumDeferred = creator.connectTCP('127.0.0.1', 1234)
    def connected(ampProto):
        return ampProto.callRemote(Sum, a=13, b=81)
    sumDeferred.addCallback(connected)
    def summed(result):
        return result['total']
    sumDeferred.addCallback(summed)

    divideDeferred = creator.connectTCP('127.0.0.1', 1234)
    def connected(ampProto):
        return ampProto.callRemote(Divide, numerator=1234, denominator=0)
    divideDeferred.addCallback(connected)
    def trapZero(result):
        result.trap(ZeroDivisionError)
        print "Divided by zero: returning INF"
        return 1e1000
    divideDeferred.addErrback(trapZero)

    def done(result):
        print 'Done with math:', result
        reactor.stop()
    defer.DeferredList([sumDeferred, divideDeferred]).addCallback(done)

if __name__ == '__main__':
    doMath()
    reactor.run()
