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

from pyunit import unittest

from twisted.python import mvc
from twisted.python import components

# simple pickled string storage to test persistence
persisted_model = ""

class MyModel(mvc.Model):
    def __init__(self, foo, random=None):
        # I hate having to explicitly initialize the super
        mvc.Model.__init__(self)
        self.foo=foo
        self.random=random

class MyView(mvc.View):        
    def __init__(self, model):
        mvc.View.__init__(self, model)
        self.model.addView(self)
        # pretend self.foo is what the user now sees on their screen
        self.foo = self.model.foo
        self.random = self.model.random

    def update_foo(self, newValue):
        # pretend self.foo is what the user actually sees on the screen
        self.foo = newValue
   
    def update_random(self, newValue):
        # pretend self.random is what the user actually sees on the screen
        self.random = newValue
    
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
components.registerAdapter(MyView, MyModel, mvc.IView)

class MyController(mvc.Controller):
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
        
        from cPickle import dumps
        persisted_model = dumps(self.model)

# Register MyController as the controller for instances of type MyModel
components.registerAdapter(MyController, MyModel, mvc.IController)

class MVCTestCase(unittest.TestCase):
    """Test MVC."""
    def setUp(self):
        self.model = MyModel("foo")

    def getView(self):
        return components.getAdapter(self.model, mvc.IView, None)

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

    def testPersistence(self):
        """See if the automatically-persisting model (persisted by the
        controller) matches our live model"""
        global persisted_model
        
        view = self.getView()
        view.twiddleControl("ASDFASDF")
        from cPickle import loads
        loadedModel = loads(persisted_model)
        self.assertEquals(loadedModel, self.model)

testCases = [MVCTestCase]
