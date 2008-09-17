from random import choice
from twisted.internet import reactor, defer
from twisted.spread import pb

class DelayedQuoteReader(pb.Root):

    def __init__(self, quoteList):
        self.quotes = quoteList

    def remote_nextQuote(self):
        d = defer.Deferred()
        d.addCallback(choice)
        reactor.callLater(2, d.callback, self.quotes)
        return d

