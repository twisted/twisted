from random import choice

from zope.interface import implementer

from TwistedQuotes import quoteproto



@implementer(quoteproto.IQuoter)
class StaticQuoter:
    """
    Return a static quote.
    """
    def __init__(self, quote):
        self.quote = quote


    def getQuote(self):
        return self.quote



@implementer(quoteproto.IQuoter)
class FortuneQuoter:
    """
    Load quotes from a fortune-format file.
    """
    def __init__(self, filenames):
        self.filenames = filenames


    def getQuote(self):
        quoteFile = file(choice(self.filenames))
        quotes = quoteFile.read().split('\n%\n')
        quoteFile.close()
        return choice(quotes)
