# -*- Python -*- 

from twisted.web.woven import model, page
from TwistedQuotes import wovenquotes
    
#__file__ is defined to be the name of this file; this is to
#get the sibling file "quotes.txt" which should be in the same directory
import os
quotefile = os.path.join(os.path.split(__file__)[0], "quotes.txt")

# ResourceScript requires us to define 'resource'. This resource is used
# to render the page.

# We're passing a dictionary of model data the template can render.
# A static title and an instance of our custom Model subclass MQuote.

model = {'quote': wovenquotes.MQuote(quotefile),
                        'title': "Woven Quotes!"}

resource = page.Page(model, templateFile="WovenQuotes.xhtml")
