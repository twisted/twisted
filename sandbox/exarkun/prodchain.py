# -*- coding: Latin-1 -*-

"""A class for combining multiple producers easily."""

from twisted.internet import interfaces

class ProducerChain:
    """Jam a pile of producers down a consumer's throat.
    
    Producers must have a "finishedProducing" attribute that is true
    once they have no more data to produce.
    """
    __implements__ = (interfaces.IProducer,)

    _onDone = None

    def beginProducing(self, consumer, producers):
        assert not self._onDone
        self.consumer = consumer
        self.producers = producers
        self.producers.reverse()
        
        self.prod = producers.pop()
        self._onDone = defer.Deferred()
        self.consumer.registerProducer(self, False)
        return self._onDone

    def resumeProducing(self):
        self.prod.resumeProducing()
        if getattr(self.prod, 'finishedProducing', False):
            if self.producers:
                self.prod = self.producers.pop()
            else:
                self.consumer.unregisterProducer()
                self._onDone.callback(self)
                self._onDone = None

    def pauseProducing(self):
        pass

    def stopProducing(self):
        if self._onDone:
            self._onDone.errback(Exception())
            self._onDone = None
