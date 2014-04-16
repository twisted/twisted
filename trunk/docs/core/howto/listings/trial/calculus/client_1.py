# -*- test-case-name: calculus.test.test_client_1 -*-

from twisted.protocols import basic
from twisted.internet import defer



class RemoteCalculationClient(basic.LineReceiver):
    def __init__(self):
        self.results = []


    def lineReceived(self, line):
        d = self.results.pop(0)
        d.callback(int(line))


    def _sendOperation(self, op, a, b):
        d = defer.Deferred()
        self.results.append(d)
        line = "%s %d %d" % (op, a, b)
        self.sendLine(line)
        return d


    def add(self, a, b):
        return self._sendOperation("add", a, b)


    def subtract(self, a, b):
        return self._sendOperation("subtract", a, b)


    def multiply(self, a, b):
        return self._sendOperation("multiply", a, b)


    def divide(self, a, b):
        return self._sendOperation("divide", a, b)
