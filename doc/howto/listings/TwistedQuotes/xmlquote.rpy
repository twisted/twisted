from twisted.web import xmlrpc
from TwistedQuotes import quoters
import os

quotefile = os.path.join(os.path.split(__file__)[0], "quotes.txt")
quoter = quoters.FortuneQuoter([quotefile])

class Quoter(xmlrpc.XMLRPC):
    
    def xmlrpc_quote(self):
        return quoter.getQuote()
    
resource = Quoter()
