# page.py

__version__ = "$Revision: 1.15 $"[11:-2]

from twisted.python import reflect
from twisted.web import resource
from twisted.web.woven import model, view, controller, interfaces, template

class Page(model.MethodModel, controller.Controller, view.View):
    __implements__ = (model.Model.__implements__, view.View.__implements__,
                      controller.Controller.__implements__)
    def __init__(self, *args, **kwargs):
        templateFile = kwargs.setdefault('templateFile', None)
        inputhandlers = kwargs.setdefault('inputhandlers', None)
        controllers = kwargs.setdefault('controllers', None)
        templateDirectory = kwargs.setdefault('templateDirectory', None)
        template = kwargs.setdefault('template', None)
                 
        del kwargs['templateFile']
        del kwargs['inputhandlers']
        del kwargs['controllers']
        del kwargs['templateDirectory']
        del kwargs['template']

        model.Model.__init__(self, *args, **kwargs)
        self.model = self

        controller.Controller.__init__(self, self.model,
                                       inputhandlers=inputhandlers,
                                       controllers=controllers)
        self.view = self
        view.View.__init__(self, self.model, controller=self,
                           templateFile=templateFile,
                           templateDirectory = templateDirectory,
                           template = template)
        self.controller = self
        self.controllerRendered = 0
    
    def renderView(self, request):
        return view.View.render(self, request,
                                doneCallback=self.gatheredControllers)

class LivePage(model.MethodModel, controller.LiveController, view.LiveView):
    # M.I. sucks.
    __implements__ = (model.Model.__implements__, view.View.__implements__,
                      controller.Controller.__implements__)
    def __init__(self, m=None, templateFile=None, inputhandlers=None, templateDirectory=None,
                 controllers=None, *args, **kwargs):
        model.Model.__init__(self, *args, **kwargs)
        if m is None:
            self.model = self
        else:
            self.model = m
        controller.LiveController.__init__(self, self.model,
                                       inputhandlers=inputhandlers,
                                       controllers=controllers)
        self.view = self
        view.View.__init__(self, self.model, controller=self,
                           templateFile=templateFile, templateDirectory=templateDirectory)
        self.controller = self
        self.controllerRendered = 0
    
    def renderView(self, request):
        return view.View.render(self, request,
                                doneCallback=self.gatheredControllers)
