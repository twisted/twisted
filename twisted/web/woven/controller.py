
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
from twisted.python import mvc
from twisted.web import resource
from twisted.web.woven import template


class WController(mvc.Controller, resource.Resource):
    """
    A simple controller that automatically passes responsibility on to the view
    class registered for the model. You can override render to perform
    more advanced template lookup logic.
    """
    __implements__ = (mvc.Controller.__implements__, resource.IResource)
    
    def __init__(self, *args, **kwargs):
        mvc.Controller.__init__(self, *args, **kwargs)
        resource.Resource.__init__(self)
    
    def setUp(self, request):
        pass

    def render(self, request):
        self.setUp(request)
        self.view = components.getAdapter(self.model, mvc.IView, None)
        self.view.setController(self)
        return self.view.render(request)

    def process(self, request, **kwargs):
        log.msg("Processing results: ", kwargs)
        return template.RESTART_RENDERING


def registerControllerForModel(controller, model):
    components.registerAdapter(controller, model, mvc.IController)
    if components.implements(controller, resource.IResource):
        components.registerAdapter(controller, model, resource.IResource)

