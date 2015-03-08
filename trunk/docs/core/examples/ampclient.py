from twisted.internet import reactor, defer, endpoints
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.protocols.amp import AMP
from ampserver import Sum, Divide


def doMath():
    destination = TCP4ClientEndpoint(reactor, '127.0.0.1', 1234)
    sumDeferred = connectProtocol(destination, AMP())
    def connected(ampProto):
        return ampProto.callRemote(Sum, a=13, b=81)
    sumDeferred.addCallback(connected)
    def summed(result):
        return result['total']
    sumDeferred.addCallback(summed)

    divideDeferred = connectProtocol(destination, AMP())
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
