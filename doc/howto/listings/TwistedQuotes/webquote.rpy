# -*- Python -*- 
from twisted.web import domtemplate
from twisted.python import domhelpers #helpers for munging the DOM


import quoters

class QuoteResource(domtemplate.DOMTemplate):
    """I am a DOMTemplate that displays a fancy quote page."""
    
    #The template; this must be valid XML (parsable by Python's DOM implementation)
    template = '''
    <html>
    <head>
      <title id="title">Title will go here</title>
      <style>
      .quote {color: green;}
      </style>
    </head>

    <body>
    
    <h1 class="title">Title will go here</h1>
    
    <pre class="quote">
    Quote will go here.
    </pre>
    
    </body></html>
    '''
    
    
    def __init__(self, filenames):
        domtemplate.DOMTemplate.__init__(self)
        self.quoter = quoters.FortuneQuoter(filenames)
        
        
    def getTemplateMethods(self):
        """
        DOMTemplate calls this to get the classes/ids/tagnames that we're interested in.
        """
        return [{'class': 'title', 'id': 'title', 'method': self.getTitle},
                {'class': 'quote', 'method': self.getQuote}]
        
    
    def getQuote(self, request, node):
        """
        Return a (hopefully amusing) quote.
        """
        domhelpers.clearNode(node)
        node.appendChild(self.d.createTextNode(self.quoter.getQuote()))
        return node

    def getTitle(self, request, node):
        """Quotes Galore!"""
        domhelpers.clearNode(node)
        node.appendChild(self.d.createTextNode("Quotes Galore!"))
        return node
    
#__file__ is defined to be the name of this file; this is to
#get the sibling file "quotes.txt" which should be in the same directory
import os
quotefile = os.path.join(os.path.split(__file__)[0], "quotes.txt")

#ResourceScript requires us to define 'resource'. This resource is used to render the page.
resource = QuoteResource([quotefile])
