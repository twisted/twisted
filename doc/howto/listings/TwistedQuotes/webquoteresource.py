from twisted.web.woven import template
from twisted.python import domhelpers #helpers for munging the DOM


from TwistedQuotes import quoters

class QuoteResource(template.DOMTemplate):
    """I am a DOMTemplate that displays a fancy quote page."""
    
    #The template; this must be valid XML (parsable by Python's DOM implementation)
    templateFile = "WebQuotes.xhtml"
    
    def __init__(self, filenames):
        template.DOMTemplate.__init__(self)
        self.quoter = quoters.FortuneQuoter(filenames)        
    
    def factory_getQuote(self, request, node):
        """
        Return a (hopefully amusing) quote.
        """
        domhelpers.clearNode(node)
        node.appendChild(self.d.createTextNode(self.quoter.getQuote()))
        return node

    def factory_getTitle(self, request, node):
        """Quotes Galore!"""
        domhelpers.clearNode(node)
        node.appendChild(self.d.createTextNode("Quotes Galore!"))
        return node
