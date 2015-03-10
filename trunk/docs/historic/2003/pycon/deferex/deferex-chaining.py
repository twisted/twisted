from twisted.internet import reactor, defer

A = defer.Deferred()
def X(result):
    B = defer.Deferred()
    reactor.callLater(2, B.callback, result)
    return B
def Y(result):
    print result
A.addCallback(X)
A.addCallback(Y)
A.callback("hello world")
reactor.run()
