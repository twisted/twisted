from twisted.spread import pb

class QuoteReader(pb.Perspective):
    def perspective_nextQuote(self):
        return self.service.quoter.getQuote()

class QuoteService(pb.Service):
    def __init__(self, quoter, serviceName, app=None):
        pb.Service.__init__(self, serviceName, app)
        self.quoter = quoter
    perspectiveClass = QuoteReader
