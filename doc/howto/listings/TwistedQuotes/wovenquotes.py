# wovenquotes

from twisted.web.woven import model, input
from TwistedQuotes import quoters


class MQuote(model.Model):
    """A class which implements IModel for a FortuneQuoter instance for a given
    filename.
    """
    def __init__(self, filename):
        model.Model.__init__(self)
        self._filename = filename
        self._quoter = quoters.FortuneQuoter([filename])
    
    def getData(self):
        """Get a random quote from the quotefile.
        """
        return self._quoter.getQuote()

    def setData(self, data):
        """Add a new quote to the quotefile.
        """
        file = open(self._filename, 'a')
        file.write('\n%\n'  + data)

