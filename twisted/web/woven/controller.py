
# Twisted, the Framework of Your Internet
# Copyright (C) 2000-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from __future__ import nested_scopes

from twisted.python import log
from twisted.python import components
from twisted.web import resource
from twisted.web.woven import interfaces


def controllerFactory(controllerClass):
    return lambda request, node, model: controllerClass(model)

def controllerMethod(controllerClass):
    return lambda self, request, node, model: controllerClass(model)


class Controller(resource.Resource):
    """
    A Controller which handles to events from the user. Such events
    are `web request', `form submit', etc.

    I should be the IResource implementor for your Models (and
    L{registerControllerForModel} makes this so).
    """

    __implements__ = (interfaces.IController, resource.IResource)

    def __init__(self, *args):
        resource.Resource.__init__(self)
        self.model = args[-1]
        self.subcontrollers = []

    def setView(self, view):
        self.view = view

    def setUp(self, request):
        """
        @type request: L{twisted.web.server.Request}
        """
        pass

    def getChild(self, name, request):
        """
        Look for a factory method to create the object to handle the
        next segment of the URL. If a wchild_* method is found, it will
        be called to produce the Resource object to handle the next
        segment of the path.
        """
        if not request.postpath:
            method = "index"
        else:
            method = request.postpath[0]
        f = getattr(self, "wchild_%s" % method, None)
        if f:
            request.prepath.append(request.postpath.pop(0))
            return f(request)
        else:
            return resource.Resource.getChild(self, name, request)

    def render(self, request, block=0):
        """
        This passes responsibility on to the view class registered for
        the model. You can override me to perform more advanced
        template lookup logic.
        """

        self.setUp(request)
        self.view = components.getAdapter(self.model, interfaces.IView, None)
        self.view.setController(self)
        for subcontroller in self.subcontrollers:
            subcontroller.handle(request)
        return self.view.render(request, block=block)

    def process(self, request, **kwargs):
        log.msg("Processing results: ", kwargs)

    def setSubmodel(self, submodel):
        self.submodel = submodel

    def handle(self, request):
        """
        By default, we don't do anything
        """
        return (None, None)

WController = Controller

def registerControllerForModel(controller, model):
    """
    Registers `controller' as an adapter of `model' for IController, and
    optionally registers it for IResource, if it implements it.

    @param controller: A class that implements L{interfaces.IController}, usually a
           L{Controller} subclass. Optionally it can implement
           L{resource.IResource}.
    @param model: Any class, but probably a L{twisted.web.woven.model.Model}
           subclass.
    """
    components.registerAdapter(controller, model, interfaces.IController)
    if components.implements(controller, resource.IResource):
        components.registerAdapter(controller, model, resource.IResource)
