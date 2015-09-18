"""Simple example of doing arbitrarily long calculations nicely in Twisted.

This is also a simple demonstration of twisted.protocols.basic.LineReceiver.
"""

from twisted.protocols import basic
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory

class LongMultiplicationProtocol(basic.LineReceiver):
    """A protocol for doing long multiplications.

    It receives a list of numbers (separated by whitespace) on a line, and
    writes back the answer.  The answer is calculated in chunks, so no one
    calculation should block for long enough to matter.
    """
    def connectionMade(self):
        self.workQueue = []
        
    def lineReceived(self, line):
        try:
            numbers = map(long, line.split())
        except ValueError:
            self.sendLine('Error.')
            return

        if len(numbers) <= 1:
            self.sendLine('Error.')
            return

        self.workQueue.append(numbers)
        reactor.callLater(0, self.calcChunk)

    def calcChunk(self):
        # Make sure there's some work left; when multiple lines are received
        # while processing is going on, multiple calls to reactor.callLater()
        # can happen between calls to calcChunk().
        if self.workQueue:
            # Get the first bit of work off the queue
            work = self.workQueue[0]
    
            # Do a chunk of work: [a, b, c, ...] -> [a*b, c, ...]
            work[:2] = [work[0] * work[1]]
    
            # If this piece of work now has only one element, send it.
            if len(work) == 1:
                self.sendLine(str(work[0]))
                del self.workQueue[0]
            
            # Schedule this function to do more work, if there's still work
            # to be done.
            if self.workQueue:
                reactor.callLater(0, self.calcChunk)


class LongMultiplicationFactory(ServerFactory):
    protocol = LongMultiplicationProtocol


if __name__ == '__main__':
    from twisted.python import log
    import sys
    log.startLogging(sys.stdout)
    reactor.listenTCP(1234, LongMultiplicationFactory())
    reactor.run()

