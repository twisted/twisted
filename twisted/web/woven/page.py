# page.py

from twisted.python import reflect
from twisted.web import resource
from twisted.web.woven import model, view, controller, interfaces, template

class Page(model.Model, controller.Controller, view.View):
    __implements__ = (model.Model.__implements__, view.View.__implements__,
                      controller.Controller.__implements__)
    def __init__(self, m=None, templateFile=None, inputhandlers=None,
                 *args, **kwargs):
        model.Model.__init__(self, *args, **kwargs)
        if m is None:
            self.model = self
        else:
            self.model = m
        controller.Controller.__init__(self, self.model,
                                       inputhandlers=inputhandlers)
        self.view = self
        view.View.__init__(self, self.model, controller=self,
                           templateFile=templateFile)
        self.controller = self
        self.controllerRendered = 0
    
    def renderView(self, request, block=0):
        return view.View.render(self, request,
                                doneCallback=self.gatheredControllers,
                                block=block)

class LivePage(model.Model, controller.LiveController, view.View):
    # M.I. sucks.
    __implements__ = (model.Model.__implements__, view.View.__implements__,
                      controller.Controller.__implements__)
    def __init__(self, m=None, templateFile=None, inputhandlers=None,
                 *args, **kwargs):
        model.Model.__init__(self, *args, **kwargs)
        if m is None:
            self.model = self
        else:
            self.model = m
        controller.LiveController.__init__(self, self.model,
                                       inputhandlers=inputhandlers)
        self.view = self
        view.View.__init__(self, self.model, controller=self,
                           templateFile=templateFile)
        self.controller = self
        self.controllerRendered = 0
    
    def wvfactory_webConduitGlue(self, request, node, m):
    	return view.View(m, templateFile="WebConduitGlue.html")

    def renderView(self, request, block=0):
        return view.View.render(self, request,
                                doneCallback=self.gatheredControllers,
                                block=block)
