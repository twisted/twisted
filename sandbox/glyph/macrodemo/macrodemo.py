

from twisted.web.woven.controller import Controller
from twisted.web.woven.model import MethodModel
from twisted.web.woven.view import View
from twisted.web.woven.widgets import ExpandMacro

class SimpleView(View):
    def wvfactory_macro(self, request, node, model):
        return ExpandMacro(
                model,
                macroFile="macros.html",
                macroFileDirectory=self.templateDirectory,
                macroName="main")


class NothingModel(MethodModel):
    pass

class MacroDemo(Controller):

    templateDirectory = "."
    viewFactory = SimpleView

    def wchild_index(self, req):
        return self.makeView(NothingModel(), "page1.html")

    def wchild_page2(self, req):
        return self.makeView(NothingModel(), "page2.html")

