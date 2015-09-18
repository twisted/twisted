# -*- test-case-name: calculus.test.test_client -*-

from twisted.protocols import basic, policies
from twisted.internet import defer



class ClientTimeoutError(Exception):
    pass



class RemoteCalculationClient(object, basic.LineReceiver, policies.TimeoutMixin):

    def __init__(self):
        self.results = []
        self._timeOut = 60

    def lineReceived(self, line):
        self.setTimeout(None)
        d = self.results.pop(0)
        d.callback(int(line))


    def timeoutConnection(self):
        for d in self.results:
            d.errback(ClientTimeoutError())
        self.transport.loseConnection()


    def _sendOperation(self, op, a, b):
        d = defer.Deferred()
        self.results.append(d)
        line = "%s %d %d" % (op, a, b)
        self.sendLine(line)
        self.setTimeout(self._timeOut)
        return d


    def add(self, a, b):
        return self._sendOperation("add", a, b)


    def subtract(self, a, b):
        return self._sendOperation("subtract", a, b)


    def multiply(self, a, b):
        return self._sendOperation("multiply", a, b)


    def divide(self, a, b):
        return self._sendOperation("divide", a, b)
