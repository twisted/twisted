
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

from twisted.python import log
from twisted.python import components
from twisted.web import resource
from twisted.web.woven import interfaces

class Controller(resource.Resource):
    """
    A Controller which translates commands the user executed on the
    view into explicit manipulations of the model. This is where the
    business logic lives.

    This passes responsibility on to the view class registered for the
    model. You can override render to perform more advanced template
    lookup logic.
    """
    
    __implements__ = (interfaces.IController, resource.IResource)
    
    def __init__(self, *args):
        resource.Resource.__init__(self)
        self.model = args[-1]

    def setView(self, view):
        self.view = view
        
    
    def setUp(self, request):
        """
        @type request: L{twisted.web.server.Request}
        """
        pass

    def render(self, request):
        self.setUp(request)
        self.view = components.getAdapter(self.model, interfaces.IView, None)
        self.view.setController(self)
        return self.view.render(request)

    def process(self, request, **kwargs):
        log.msg("Processing results: ", kwargs)

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

