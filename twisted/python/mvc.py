
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
"""

# TODO: Warning, Danger, Danger, Warning
# This module creates lots of circular references
# Do we care?

from twisted.python import components

# Should these interfaces be somewhere else?

class IModel(components.Interface):
    """A MVC Model."""
    def addView(self, view):
        """Add a view for the model to keep track of."""
        raise NotImplementedError

    def removeView(self, view):
        """Remove a view that the model no longer should keep track of."""
        raise NotImplementedError

    def notify(self, changed=None):
        """
        Notify all views that something was changed on me.
        Passing a dictionary of {'attribute': 'new value'} in changed
        will pass this dictionary to the view for increased performance.
        If you don't want to do this, don't, and just use the traditional
        MVC paradigm of querying the model for things you're interested
        in.
        """
        raise NotImplementedError

class IView(components.Interface):
    """A MVC View"""
    def __init__(self, model, controller=None):
        """
        A view must be told what it's model is, and may be told what it's
        controller is, but can also look up it's controller if none specified.
        """
        raise NotImplementedError

    def draw(self):
        """Hook subclasses can override to implement drawing the whole view"""

    def modelChanged(self, changed):
        """
        Dispatch changed messages to any update_* methods which
        may have been defined, then pass the update notification on
        to the controller.
        """

    def controllerFactory(self):
        """
        Hook for subclasses to customize the controller that is associated
        with the model associated with this view.
        
        Default behavior: Look up a component that implements IController
        for the self.model instance.
        """
        
    def setController(self, controller):
        """Set the controller that this view is related to."""

class IController(components.Interface):
    """A MVC Controller"""
    def setView(self, view):
        """
        Set the view that this controller is related to.
        """

# Should all these docstrings be duplicated in the implementation
# of the interfaces?

class Model:
    """
    A Model which keeps track of views which are looking at it in order
    to notify them when the model changes.
    """
    __implements__ = IModel
    
    def __init__(self, *args, **kwargs):
        self.views = []
        self.initialize(*args, **kwargs)
    
    def initialize(self, *args, **kwargs):
        """
        Hook for subclasses to initialize themselves without having to
        mess with the __init__ chain.
        """
        pass

    def addView(self, view):
        """
        Add a view for the model to keep track of.
        """
        self.views.append(view)
    
    def removeView(self, view):
        """
        Remove a view that the model no longer should keep track of.
        """
        self.views.remove(view)
    
    def notify(self, changed=None):
        """
        Notify all views that something was changed on me.
        Passing a dictionary of {'attribute': 'new value'} in changed
        will pass this dictionary to the view for increased performance.
        If you don't want to do this, don't, and just use the traditional
        MVC paradigm of querying the model for things you're interested
        in.
        """
        if changed is None: changed = {}
        for view in self.views:
            view.modelChanged(changed)

    def __eq__(self, other):
        if other is None: return 0
        for elem in self.__dict__.keys():
            if elem is "views": continue
            if getattr(self, elem) != getattr(other, elem, None):
                return 0
        else:
            return 1
    
    def __ne__(self, other):
        if other is None: return 1
        for elem in self.__dict__.keys():
            if elem is "views": continue
            if getattr(self, elem) == getattr(other, elem, None):
                return 0
        else:
            return 1


class View:
    """
    A View which tracks a model and displays it's contents to the user.
    """
    __implements__ = IView
    
    def __init__(self, model, controller=None, *args, **kwargs):
        """
        A view must be told what it's model is, and may be told what it's
        controller is, but can also look up it's controller if none specified.
        """
        model.addView(self)
        self.model = model
        if controller:
            self.controller = controller
        else:
            self.controller = self.controllerFactory(model)
        self.initialize(*args, **kwargs)
    
    def initialize(self):
        """
        Hook subclasses can override to set up the initial view
        after the class is done initializing, without overriding __init__
        """
        pass

    def modelChanged(self, changed):
        """
        Dispatch changed messages to any update_* methods which
        may have been defined, then pass the update notification on
        to the controller.
        """
        for name in changed.keys():
            handler = getattr(self, 'update_' + name, None)
            if handler:
                apply(handler, (changed[name],))

    def controllerFactory(self, model):
        """
        Hook for subclasses to customize the controller that is associated
        with the model associated with this view.
        """
        # TODO: Decide what to do as a default Controller
        # if you don't need to use one...
        # Something that ignores all messages?
        controller = components.getAdapter(model, IController, None)
        if controller:
            controller.setView(self)
        return controller
        
    def setController(self, controller):
        self.controller = controller

class Controller:
    """
    A Controller which translates commands the user executed on the
    view into explicit manipulations of the model. This is where the
    business logic lives.
    """
    __implements__ = IController
    
    def __init__(self, model):
        self.model = model

    def setView(self, view):
        self.view = view
