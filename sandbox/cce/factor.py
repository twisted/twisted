from __future__ import generators
from twisted.protocols import basic
from twisted.internet import reactor
from twisted.internet import protocol
from twisted.internet import defer

import Queue
import math
import sys

def withoutFlow():
    """
        An example protocol which does not use the flow module
    """
    # Factor a number, and toss the results into the given queue
    # Signal the end of factorization by adding None to the queue
    def factor(n, q):
        i = 1
        while i < math.ceil(n ** 0.5):
            if n % i == 0:
                q.put(i)
                q.put(n / i)
            i += 1
        q.put(None)
    
    # Accept numbers from a client, have them factored in a separate thread,
    # and send the factors back as they become available.
    class FactoringServer(basic.LineReceiver):
        def lineReceived(self, line):
            try:
                value = long(line)
            except ValueError:
                self.sendLine('ERROR')
            else:
                q = Queue.Queue()
                reactor.callInThread(factor, value, q)
                reactor.callLater(0.1, self.pollQueue, value, q)
        
        # Check the factor queue for any possible new values
        # Send any that are there to the client
        def pollQueue(self, value, q):
            while not q.empty():
                factor = q.get(0)
                if factor is None:
                    self.sendLine('%d: DONE' % (value,))
                    return
                else:
                    self.sendLine('%d: %d' % (value, factor))
            reactor.callLater(0.1, self.pollQueue, value, q)
    
    def printFactorList(lst, orig):
        print '%d: %s' % (orig, ', '.join(map(str, lst)))
    
    # Connect to a FactoringServer and ask for a number to be factored
    # When the results arrive, have them printed out.
    #
    # findFactors() / lineReceived() 
    class FactoringClient(basic.LineReceiver):
        def __init__(self):
            self.live = {}
        
        def connectionMade(self):
            d = self.findFactors(self.factory.value)
            d.addCallback(printFactorList, self.factory.value)
            d.addCallback(lambda x: self.transport.loseConnection())
    
        def connectionLost(self, reason):
            reactor.stop()
        
        def findFactors(self, number):
            if number in self.live:
                raise RuntimeError, "You already asked for that."
    
            d = defer.Deferred()
            self.live[number] = ([], d)
            self.sendLine(str(number))
            return d
        
        def lineReceived(self, line):        
            parts = line.split(': ')
            value = long(parts[0])
            if parts[1] == 'DONE':
                factors, d = self.live[value]
                d.callback(factors)
                del self.live[value]
            else:
                self.live[value][0].append(long(parts[1]))
    
    # Set up a factoring server
    def server(port=6543):
        f = protocol.ServerFactory()
        f.protocol = FactoringServer
        return reactor.listenTCP(port, f)
    
    # Set up a factoring client
    def client(n, port=6543):
        f = protocol.ClientFactory()
        f.protocol = FactoringClient
        f.value = n
        return reactor.connectTCP('localhost', port, f)

    return (FactoringClient, FactoringServer)

def withFlow():
    """
        The same example refactored to use generators/flow
    """
    from twisted.flow import flow

    # Return the factors of a given number as a iterable object
    def factor(n):
        i = 1
        while i < math.ceil(n ** 0.5):
            if n % i == 0:
                yield i
                yield n / i
            i += 1
            if not i % 1000:
                yield flow.Cooperate()
    
    # Write the factors out to an output stream...
    def writefactor(n, write):
        factors = flow.wrap(factor(n))
        yield factors
        for fac in factors:
            write('%d: %d' % (n, fac))
            yield factors
        write('%d: DONE' % (n,))
    
    # accept numbers from a client, have them factored, and send back the factors
    class FactoringServer(basic.LineReceiver):
        def lineReceived(self, line):
            try:
                value = long(line)
            except ValueError:
                self.sendLine('ERROR')
            else:
                flow.Deferred(writefactor(value, self.sendLine))
    
    # handle the lines that are recieved
    def receiveLines(lines, live):
        yield lines
        for line in lines:
            parts  = line.split(': ')
            value  = long(parts[0])
            factors = live[value]
            if parts[1] == 'DONE':
                del live[value]
                yield (value, factors)
                if not live:
                    return
            else:
                factors.append(long(parts[1]))
            yield lines
    
    # for each pair yielded by receiveLines, print it
    def printResults(lines, live):
        results = flow.wrap(receiveLines(lines, live))
        yield results
        for (value, factors) in results:
            print '%d: %s' % (value, ', '.join(map(str, factors)))
            yield results
    
    class FactoringClient(basic.LineReceiver):
        def __init__(self):
            self.live = {}
        def connectionLost(self, reason):
            reactor.stop()
        
        def connectionMade(self):
            # create a callback object, and register it to recieve lines
            cb = flow.Callback()
            self.lineReceived = cb.result
            #
            self.findFactors(self.factory.value)
            d = flow.Deferred(printResults(cb,self.live))
            d.addCallback(lambda _: self.transport.loseConnection())
    
        def findFactors(self, number):
            if number in self.live:
                raise RuntimeError, "You already asked for that."
            self.live[number] = []
            self.sendLine(str(number))

    return (FactoringClient, FactoringServer)


# Set up a server and client and get them talking to each other
def main(tpl):

    FactoringClient, FactoringServer = tpl

    # Set up a factoring server
    def server(port=6543):
        f = protocol.ServerFactory()
        f.protocol = FactoringServer
        return reactor.listenTCP(port, f)
        
    # Set up a factoring client
    def client(n, port=6543):
        f = protocol.ClientFactory()
        f.protocol = FactoringClient
        f.value = n
        return reactor.connectTCP('localhost', port, f)

    try:
        value = long(sys.argv[1])
    except:
        value = 10
    
    server()
    client(value)
    reactor.run()

if __name__ == '__main__':
    main(withFlow())
    main(withoutFlow())
