from twisted.python import log
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, ContentDecoderAgent, GzipDecoder

class BeginningPrinter(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.remaining = 1024 * 10


    def dataReceived(self, bytes):
        if self.remaining:
            display = bytes[:self.remaining]
            print 'Some data received:'
            print display
            self.remaining -= len(display)


    def connectionLost(self, reason):
        print 'Finished receiving body:', reason.type, reason.value
        self.finished.callback(None)



def printBody(response):
    finished = Deferred()
    response.deliverBody(BeginningPrinter(finished))
    return finished


def main():
    agent = ContentDecoderAgent(Agent(reactor), [('gzip', GzipDecoder)])

    d = agent.request('GET', 'http://www.yahoo.com/')
    d.addCallback(printBody)
    d.addErrback(log.err)
    d.addCallback(lambda ignored: reactor.stop())
    reactor.run()

if __name__ == "__main__":
    main()
