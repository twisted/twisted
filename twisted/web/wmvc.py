# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""
webmvc.py

The webmvc module collects together most of the modules and functions you will need to use Twisted's model view controller architecture for the web.

WebMVC has been Deprecated and is now named Woven. The objects contained in this module are now defined in three submodules, woven.model, woven.view, and woven.controller.
"""

from twisted.python import log
log.write("DeprecationWarning: twisted.web.wmvc has been renamed twisted.web.woven. It has also been split into template, model, view, and controller modules.\n")

from twisted.python import mvc
from twisted.python import components
from twisted.web import resource
from twisted.web.woven import template
from twisted.web.woven import widgets
from twisted.web.woven import input

domtemplate = template
domwidgets = widgets
domhandlers = input
dominput = input

from twisted.web.woven import model
from twisted.web.woven import view
from twisted.web.woven import controller

WModel = model.WModel
WView = view.WView
WController = controller.WController

registerViewForModel = view.registerViewForModel
registerControllerForModel = controller.registerControllerForModel
