from zope.interface import implementer

from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer


@implementer(IBodyProducer)
class BytesProducer:
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass
