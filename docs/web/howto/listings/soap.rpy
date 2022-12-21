from twisted.web import soap
import os

def getQuote():
    return "That beverage, sir, is off the hizzy."

class Quoter(soap.SOAPPublisher):
    """Publish one method, 'quote'."""

    def soap_quote(self):
        return getQuote()

resource = Quoter()                 
