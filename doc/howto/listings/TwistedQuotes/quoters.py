class AbstractQuoter:
    def getQuote(self):
        raise NotImplementedError()

class StaticQuoter(AbstractQuoter):
    def __init__(self, quote):
        self.quote = quote
    def getQuote(self):
        return self.quote

from random import choice

class FortuneQuoter(AbstractQuoter):
    def __init__(self, filenames):
        self.filenames = filenames
    def getQuote(self):
     return choice(open(choice(self.filenames)).read().split('\n%'))
