# webmvcquotes

from twisted.web import wmvc
from twisted.web import domwidgets
from twisted.web import domhandlers
from twisted.python import domhelpers

import quoters


class MQuote(wmvc.WModel):
    def __init__(self, filename):
        self._filename = filename
        self._quoter = quoters.FortuneQuoter([filename])
        self.quote = ""
        self.title = "Quotes Galore!"
    
    def updateQuote(self):
        self.quote = self._quoter.getQuote()

    def getQuoteFilename(self):
        return self._filename


class QuoteWidget(domwidgets.Widget):
    def generateDOM(self, request, node):
        """
        Generate DOM to represent a quote.
        
        Since self is a Widget, I can use the higher level widget API to add a 
        Text widget to self. I then rely on Widget.generateDOM to convert
        from Widgets into the Document Object Model.
        """
        quote = self.getData()
        self.add(domwidgets.Text(quote))
        return domwidgets.Widget.generateDOM(self, request, node)


class VQuote(wmvc.WView):
    templateFile = "WebMVCQuotes.xhtml"

    def setUp(self, request, document):
        """
        Set things up for this request.
        """
        self.model.updateQuote()

    def factory_quote(self, request, node):
        """Create a widget which knows how to render my model's quote."""
        domhelpers.clearNode(node)
        return QuoteWidget(self.model)

    def factory_title(self, request, node):
        """Create a widget which knows how to render my model's title."""
        domhelpers.clearNode(node)
        return domwidgets.Text(self.model)


class NewQuoteHandler(domhandlers.SingleValue):
    def check(self, request, data):
        if data:
            return 1

    def commit(self, request, node, newQuote):
        print "committing new quote", `newQuote`
        file = open(self.model.getQuoteFilename(), 'a')
        file.write('\n%'  + newQuote)


class CQuote(wmvc.WController):
    def factory_newQuote(self, model):
        """Create a handler which knows how to verify input in a form with the
        name "newQuote"."""
        return NewQuoteHandler(model)


wmvc.registerViewForModel(VQuote, MQuote)
wmvc.registerControllerForModel(CQuote, MQuote)
