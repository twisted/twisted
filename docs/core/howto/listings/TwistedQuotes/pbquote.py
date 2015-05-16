from twisted.spread import pb

class QuoteReader(pb.Root):

    def __init__(self, quoter):
        self.quoter = quoter

    def remote_nextQuote(self):
        return self.quoter.getQuote()

