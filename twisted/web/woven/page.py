# page.py

from twisted.web import resource
from twisted.web.woven import model, view, controller

class Page(model.Model, view.View, controller.Controller):
    __implements__ = resource.IResource
    def __init__(self, m=None, templateFile=None, inputhandlers=None, *args, **kwargs):
        model.Model.__init__(self, *args, **kwargs)
        if m is None:
            self.model = self
        else:
            self.model = m
        self.view = self
        view.View.__init__(self, self.model, controller=self, templateFile=templateFile)
        controller.Controller.__init__(self, self.model, inputhandlers=inputhandlers)
        self.controllerRendered = 0

    def render(self, request, block=0):
        """
        This passes responsibility on to the view class registered for
        the model. You can override me to perform more advanced
        template lookup logic.
        """
        # Handle any inputhandlers that were passed in to the controller first
        for ih in self._inputhandlers:
            ih._parent = self
            ih.handle(request)
        return view.View.render(self, request, doneCallback=self.gatheredControllers, block=block)
