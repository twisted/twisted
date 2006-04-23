from zope.interface import Interface, implements

from random import choice


class IQuoter(Interface):
    """An object that returns quotes."""
    
    def getQuote():
        """Return a quote."""


class StaticQuoter:
    """Return a static quote."""
    
    implements(IQuoter)
    
    def __init__(self, quote):
        self.quote = quote
    
    def getQuote(self):
        return self.quote


class FortuneQuoter:
    """Load quotes from a fortune-format file."""
    
    implements(IQuoter)
    
    def __init__(self, filenames):
        self.filenames = filenames

    def getQuote(self):
        return choice(open(choice(self.filenames)).read().split('\n%\n'))
