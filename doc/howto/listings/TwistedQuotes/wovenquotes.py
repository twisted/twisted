# wovenquotes

from twisted.web.woven import model, view, controller
from twisted.web.woven import widgets, input
from twisted.python import domhelpers

from TwistedQuotes import quoters


class MQuote(model.WModel):
    def __init__(self, filename):
        model.WModel.__init__(self)
        self._filename = filename
        self._quoter = quoters.FortuneQuoter([filename])
        self.quote = ""
        self.title = "Quotes Galore!"
    
    def updateQuote(self):
        self.quote = self._quoter.getQuote()

    def getQuoteFilename(self):
        return self._filename


class QuoteWidget(widgets.Widget):
    def setUp(self, request, node, data):
        """
        Set up this Widget object before it gets rendered into HTML.
        
        Since self is a Widget, I can use the higher level widget API to add a 
        Text widget to self. I then rely on Widget.generateDOM to convert
        from Widgets into the Document Object Model.
        """
        self.add(widgets.Text(data))


class VQuote(view.WView):
    templateFile = "WovenQuotes.xhtml"

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
        return widgets.Text(self.model)


class NewQuoteHandler(input.SingleValue):
    def check(self, request, data):
        if data:
            return 1

    def commit(self, request, node, newQuote):
        print "committing new quote", `newQuote`
        file = open(self.model.getQuoteFilename(), 'a')
        file.write('\n%\n'  + newQuote)


class CQuote(controller.WController):
    def factory_newQuote(self, model):
        """Create a handler which knows how to verify input in a form with the
        name "newQuote"."""
        return NewQuoteHandler(model)


view.registerViewForModel(VQuote, MQuote)
controller.registerControllerForModel(CQuote, MQuote)
