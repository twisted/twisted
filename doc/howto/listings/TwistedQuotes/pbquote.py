from twisted.spread import pb

class QuoteReader(pb.Perspective):
    def perspective_nextQuote(self):
        return self.service.quoter.getQuote()

class QuoteService(pb.Service):
    def __init__(self, quoter, serviceName, serviceParent, authorizer):
        pb.Service.__init__(self, serviceName, serviceParent, authorizer)
        self.quoter = quoter
    perspectiveClass = QuoteReader
