# -*- test-case-name: calculus.test.test_client -*-

from twisted.internet import defer
from twisted.protocols import basic, policies


class ClientTimeoutError(Exception):
    pass


class RemoteCalculationClient(basic.LineReceiver, policies.TimeoutMixin):
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
        line = f"{op} {a} {b}".encode()
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
