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

"""Test cases for Twisted Model-View-Controller architecture."""

import random

try:
    import cPickle as pickle
except ImportError:
    import pickle

from twisted.trial import unittest

from twisted.web.woven import model, view, controller, interfaces
from twisted.python import components

# simple pickled string storage to test persistence
persisted_model = ""

class MyModel(model.Model):
    def __init__(self, foo, random=None):
        # I hate having to explicitly initialize the super
        model.Model.__init__(self)
        self.foo=foo
        self.random=random

class MyView(view.View):        
    def __init__(self, model, *args, **kwargs):
        view.View.__init__(self, model, *args, **kwargs)
        self.model.addView(self)
        # pretend self.foo is what the user now sees on their screen
        self.foo = self.model.foo
        self.random = self.model.random
        self.controller = components.getAdapter(self.model, interfaces.IController, None)

    def modelChanged(self, changed):
        if changed.has_key('foo'):
            self.foo = changed['foo']
        if changed.has_key('random'):
            self.random = changed['random']

    def twiddleControl(self, newValue):
        """
        The user twiddled a control onscreen, causing this event
        """
        self.controller.setFoo(newValue)
    
    def pushButton(self):
        """
        The user hit a button onscreen, causing this event
        """
        return self.controller.doRandom()

# Register MyView as the view for instances of type MyModel
components.registerAdapter(MyView, MyModel, interfaces.IView)

class MyController(controller.Controller):
    def setFoo(self, newValue):
        self.model.foo = newValue
        self.model.notify({'foo': newValue})
        self.persist()
    
    def doRandom(self):
        rnd = random.choice(range(100))
        self.model.random = rnd
        self.model.notify({'random': rnd})
        self.persist()
        return rnd
    
    def persist(self):
        """
        Save the model object to persistent storage
        """
        global persisted_model
        
        persisted_model = pickle.dumps(self.model)

# Register MyController as the controller for instances of type MyModel
components.registerAdapter(MyController, MyModel, interfaces.IController)

class MVCTestCase(unittest.TestCase):
    """Test MVC."""
    def setUp(self):
        self.model = MyModel("foo")

    def getView(self):
        return components.getAdapter(self.model, interfaces.IView, None)

    def testViewConstruction(self):
        view = self.getView()
        self.assert_(isinstance(view, MyView))

    def testControllerConstruction(self):
        view = self.getView()
        self.assert_(isinstance(view.controller, MyController))
    
    def testModelManipulation(self):
        view = self.getView()
        view.twiddleControl("bar")
        self.assertEquals("bar", self.model.foo)
    
    def testMoreModelManipulation(self):
        view = self.getView()
        value = view.pushButton()
        self.assertEquals(value, self.model.random)

    def testViewManipulation(self):
        """When the model updates the view should too"""
        view = self.getView()
        view.twiddleControl("bar")
        self.assertEquals("bar", view.foo)
    
    def testMoreViewManipulation(self):
        """When the model updates the view should too"""
        view = self.getView()
        value = view.pushButton()
        self.assertEquals(value, view.random)


testCases = [MVCTestCase]
