# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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
