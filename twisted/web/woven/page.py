# page.py

from twisted.web import resource
from twisted.web.woven import model, view, controller

class Page(model.Model, view.View, controller.Controller):
    __implements__ = (model.Model.__implements__, view.View.__implements__, controller.Controller.__implements__)
    def __init__(self, m=None, templateFile=None, inputhandlers=None, *args, **kwargs):
        model.Model.__init__(self, *args, **kwargs)
        if m is None:
            self.model = self
        else:
            self.model = m
        self.view = self
        controller.Controller.__init__(self, self.model, inputhandlers=inputhandlers)
        view.View.__init__(self, self.model, controller=self, templateFile=templateFile)
        self.controllerRendered = 0

    def render(self, request, block=0):
        """
        Trigger any inputhandlers that were passed in to this Page, then delegate
        to the View for traversing the DOM. Finally, call gatheredControllers to
        deal with any InputHandlers that were constructed from any controller=
        tags in the DOM. gatheredControllers will render the page to the browser
        when it is done.
        """
        # Handle any inputhandlers that were passed in to the controller first
        for ih in self._inputhandlers:
            ih._parent = self
            ih.handle(request)
        return view.View.render(self, request, doneCallback=self.gatheredControllers, block=block)
