from twisted.python import components

from random import choice


class IQuoter(components.Interface):
    """An object that returns quotes."""
    
    def getQuote(self):
        """Return a quote."""


class StaticQuoter:
    """Return a static quote."""
    
    __implements__ = IQuoter
    
    def __init__(self, quote):
        self.quote = quote
    
    def getQuote(self):
        return self.quote


class FortuneQuoter:
    """Load quotes from a fortune-format file."""
    
    __implements__ = IQuoter
    
    def __init__(self, filenames):
        self.filenames = filenames

    def getQuote(self):
        return choice(open(choice(self.filenames)).read().split('\n%\n'))
