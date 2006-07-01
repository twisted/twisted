# -*- test-case-name: twisted.web.test.test_woven -*-
#
# page.py

__version__ = "$Revision: 1.23 $"[11:-2]

from twisted.python import reflect
from twisted.web import resource
from twisted.web.woven import model, view, controller, interfaces, template

class Page(model.MethodModel, controller.Controller, view.View):
    """
    @cvar appRoot: Set this to True if you want me to call
          request.rememberRootURL() in my getChild, so you can later use
          request.getRootURL() to get the URL to this "application"'s root
          resource. (You don't have to worry if there will be multiple
          instances of this Page involved in a single request; I'll only
          call it for the upper-most instance).
    """

    appRoot = False

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
        if len(args):
            self.model = args[0]
        else:
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

    def getChild(self, name, request):
        # Don't call the rememberURL if we already did once; That way
        # we can support an idiom of setting appName as a class
        # attribue *even if* the same class is used more than once in
        # a hierarchy of Pages.
        if self.appRoot and not request.getRootURL():
            request.rememberRootURL()
        return controller.Controller.getChild(self, name, request)


    def renderView(self, request):
        return view.View.render(self, request,
                                doneCallback=self.gatheredControllers)

class LivePage(model.MethodModel, controller.LiveController, view.LiveView):

    appRoot = False

    def __init__(self, m=None, templateFile=None, inputhandlers=None,
                 templateDirectory=None, controllers=None, *args, **kwargs):
        template = kwargs.setdefault('template', None)
        del kwargs['template']

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
                           templateFile=templateFile,
                           templateDirectory=templateDirectory,
                           template=template)
        self.controller = self
        self.controllerRendered = 0


    def getChild(self, name, request):
        # Don't call the rememberPath if we already did once; That way
        # we can support an idiom of setting appName as a class
        # attribue *even if* the same class is used more than once in
        # a hierarchy of Pages.
        if self.appRoot and not request.getRootURL():
            request.rememberRootURL()
        return controller.Controller.getChild(self, name, request)

    def renderView(self, request):
        return view.View.render(self, request,
                                doneCallback=self.gatheredControllers)
