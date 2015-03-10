from random import choice

from zope.interface import implements

from TwistedQuotes import quoteproto



class StaticQuoter:
    """
    Return a static quote.
    """

    implements(quoteproto.IQuoter)

    def __init__(self, quote):
        self.quote = quote


    def getQuote(self):
        return self.quote



class FortuneQuoter:
    """
    Load quotes from a fortune-format file.
    """
    implements(quoteproto.IQuoter)

    def __init__(self, filenames):
        self.filenames = filenames


    def getQuote(self):
        quoteFile = file(choice(self.filenames))
        quotes = quoteFile.read().split('\n%\n')
        quoteFile.close()
        return choice(quotes)
