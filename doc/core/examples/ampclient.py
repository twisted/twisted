from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator
from twisted.protocols import amp
from ampserver import Sum

def didSum(theSum):
    print 'Hooray!  13 + 81 =', theSum
    reactor.stop()

ClientCreator(reactor, amp.AMP).connectTCP(
        '127.0.0.1', 1234).addCallback(
            lambda p: p.callRemote(Sum, a=13, b=81)).addCallback(
                lambda result: result['total']).addCallback(didSum)
reactor.run()
