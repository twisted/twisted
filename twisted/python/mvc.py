
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
A simple Model-View-Controller framework for separating
presentation, business logic, and data.

A google search reveals several interesting pages to refer
to while designing this implementation:

http://www.object-arts.com/EducationCentre/Overviews/MVC.htm

Model-View-Presenter is a slightly newer concept developed by IBM
in the early-mid nineties and now used extensively in Dolphin SmallTalk:

http://www.object-arts.com/EducationCentre/Overviews/ModelViewPresenter.htm

Pretty pictures, for sure. I'll try to keep this implementation simple
while trying to learn as much as possible from previous implementations.

This module creates many circular references. It is therefore recommended
that subclasses do not implement a __del__ method.
"""

from twisted.web.woven import model, view, controller, interfaces

IModel = interfaces.IModel
IView = interfaces.IView
IController = interfaces.IController

Model = model.Model
View = view.View
Controller = controller.Controller

import warnings
warnings.warn('twisted.python.mvc is deprecated -- use twisted.web.woven.{model,view,controller}',
              stacklevel=2)
