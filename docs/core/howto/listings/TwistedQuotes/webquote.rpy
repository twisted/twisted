# -*- Python -*- 

from TwistedQuotes import webquoteresource
    
#__file__ is defined to be the name of this file; this is to
#get the sibling file "quotes.txt" which should be in the same directory
import os
quotefile = os.path.join(os.path.split(__file__)[0], "quotes.txt")

#ResourceScript requires us to define 'resource'.
#This resource is used to render the page.
resource = webquoteresource.QuoteResource([quotefile])
