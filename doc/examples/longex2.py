"""Example of doing arbitarily long calculations nicely in Twisted.

This is also a simple demonstration of twisted.protocols.basic.LineReceiver.
This example uses generators to do the calculation. It also tries to be
a good example in division of responsibilities:
- The protocol handles the wire layer, reading in lists of numbers
  and writing out the result.
- The factory decides on policy, and has relatively little knowledge
  of the details of the protocol. Other protocols can use the same
  factory class by intantiating and setting .protocol
- The factory does little job itself: it is mostly a policy maker.
  The 'smarts' are in free-standing functions which are written
  for flexibility.

The goal is for minimal dependencies:
- You can use runIterator to run any iterator inside the Twisted
  main loop.
- You can use multiply whenever you need some way of multiplying
  numbers such that the multiplications will happen asynchronously,
  but it is your responsibility to schedule the multiplications.
- You can use the protocol with other factories to implement other
  functions that apply to arbitrary lists of longs.
- You can use the factory with other protocols for support of legacy
  protocols. In fact, the factory does not even have to be used as
  a protocol factory. Here are easy ways to support the operation
  over XML-RPC and PB.

class Multiply(xmlrpc.XMLRPC):
    def __init__(self): self.factory = Multiplication()
    def xmlrpc_multiply(self, *numbers):
        return self.factory.calc(map(long, numbers))

class Multiply(pb.Referencable):
    def __init__(self): self.factory = Multiplication()
    def remote_multiply(self, *numbers):
        return self.factory.calc(map(long, numbers))

Note:
Multiplying zero numbers is a perfectly sensible operation, and the
result is 1. In that, this example departs from doc/examples/longex.py,
which errors out when trying to do this.
"""
from __future__ import generators
from twisted.protocols import basic
from twisted.internet import defer, protocol

def runIterator(reactor, iterator):
    try:
        iterator.next()
    except StopIteration:
        pass
    else:
        reactor.callLater(0, runIterator, reactor, iterator)

def multiply(numbers):
    d = defer.Deferred()
    def _():
        acc = 1
        while numbers:
            acc *= numbers.pop()
            yield None
        d.callback(acc)
    return d, _()

class Numbers(basic.LineReceiver):
    """Protocol for reading lists of numbers and manipulating them.

    It receives a list of numbers (seperated by whitespace) on a line, and
    writes back the answer.  The exact algorithm to use depends on the
    factory. It should return an str-able Deferred.
    """
    def lineReceived(self, line):
        try:
            numbers = map(long, line.split())
        except ValueError:
            self.sendLine('Error.')
            return
        deferred = self.factory.calc(numbers)
        deferred.addCallback(str)
        deferred.addCallback(self.sendLine)

class Multiplication(protocol.ServerFactory):
    """Factory for multiplying numbers.

    It provides a function which calculates the multiplication
    of a list of numbers. The function destroys its input.
    Note that instances of this factory can use other formats
    for transmitting the number lists, as long as they set
    correct protoocl values.
    """
    protocol = Numbers
    def calc(self, numbers):
        deferred, iterator = multiply(numbers)
        from twisted.internet import reactor
        runIterator(reactor, iterator)
        return deferred

if __name__ == '__main__':
    from twisted.internet import reactor
    reactor.listenTCP(1234, Multiplication())
    reactor.run()
