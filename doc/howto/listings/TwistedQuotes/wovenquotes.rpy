# -*- Python -*- 

from TwistedQuotes import wovenquotes
    
#__file__ is defined to be the name of this file; this is to
#get the sibling file "quotes.txt" which should be in the same directory
import os
quotefile = os.path.join(os.path.split(__file__)[0], "quotes.txt")

# Construct a model object which will contain the data for display by the
# web page
model = wovenquotes.MQuote(quotefile)

# ResourceScript requires us to define 'resource'. This resource is used
# to render the page.
resource = wovenquotes.CQuote(model)

# The CQuote controller will look up a View (VQuote) and call render()
# on it, rendering the DOMTemplate
