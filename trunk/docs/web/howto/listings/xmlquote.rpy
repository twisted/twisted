from twisted.web import xmlrpc
import os

def getQuote():
    return "What are you talking about, William?"

class Quoter(xmlrpc.XMLRPC):
    
    def xmlrpc_quote(self):
        return getQuote()
    
resource = Quoter()
