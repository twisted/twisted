
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

import types, weakref

from twisted.python import components, reflect

from twisted.web.woven import interfaces


def adaptToIModel(m, parent, submodel):
    adapted = components.getAdapter(m, interfaces.IModel, None)
    if adapted is None:
        adapted = Wrapper(m)
    adapted.parent = parent
    adapted.name = submodel
    return adapted


class Model:
    """
    A Model which keeps track of views which are looking at it in order
    to notify them when the model changes.
    """
    __implements__ = interfaces.IModel
    
    def __init__(self, *args, **kwargs):
        self.views = []
        self.subviews = {}
        self.initialize(*args, **kwargs)
    
    def __getstate__(self):
        self.views = []
        self.subviews = {}
        return self.__dict__
    
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
        if view not in self.views:
            self.views.append(weakref.ref(view))
    
    def addSubview(self, name, subview):
        subviewList = self.subviews.get(name, [])
        subviewList.append(weakref.ref(subview))
        self.subviews[name] = subviewList

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
        retVal = []
        for view in self.views:
            ref = view()
            if ref is not None:
                retVal.append(ref.modelChanged(changed))
        for key, value in self.subviews.items():
            if changed.has_key(key):
                for item in value:
                    ref = item()
                    if ref is not None:
                        retVal.append(ref.modelChanged(changed))
        return retVal

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

    protected_names = ['initialize', 'addView', 'addSubview', 'removeView', 'notify', 'getSubmodel', 'setSubmodel', 'getData', 'setData']

    def lookupSubmodel(self, submodelName):
        """
        Look up a full submodel name. I will split on `/' and call
        L{getSubmodel} on each element in the 'path'.

        Override me if you don't want 'traversing'-style lookup, but
        would rather like to look up a model based on the entire model
        name specified.

        If you override me to return Deferreds, make sure I look up
        values in a cache (created by L{setSubmodel}) before doing a
        regular Deferred lookup.

        XXX: Move bits of this docstring to interfaces.py
        """
        if not submodelName:
            return self.getData()

        submodelList = submodelName.split('/')  #[:-1]
#         print "submodelList", submodelList
        currentModel = adapted = self
        for element in submodelList:
            parentModel = currentModel
            currentModel = currentModel.getSubmodel(element)
            if currentModel is None:
                return None
            adapted = components.getAdapter(currentModel, interfaces.IModel, None)
            if adapted is None:
                adapted = Wrapper(currentModel)
            #assert adapted is not None, "No IModel adapter registered for %s" % currentModel
            adapted.parent = parentModel
            adapted.name = element
            if isinstance(currentModel, defer.Deferred):
                return adapted
            currentModel = adapted
        return adapted

    
    def getSubmodel(self, name):
        """
        Get the submodel `name' of this model. If I ever return a
        Deferred, then I ought to check for cached values (created by
        L{setSubmodel}) before doing a regular Deferred lookup.
        """
        if name and name[0] != '_' and name not in self.protected_names:
            if hasattr(self, name):
                m = getattr(self, name)
                return adaptToIModel(m, self, name)
            return None

    def setSubmodel(self, name, value):
        """
        Set a submodel on this model. If getSubmodel or lookupSubmodel
        ever return a Deferred, I ought to set this in a place that
        lookupSubmodel/getSubmodel know about, so they can use it as a
        cache.
        """
        if name[0] != '_' and name not in self.protected_names:
            setattr(self, name, value)

    def getData(self):
        return self
    
    def setData(self, data):
        if hasattr(self, 'parent'):
            self.parent.setSubmodel(self.name, data)
        if hasattr(self, 'orig'):
            self.orig = data
        
#            raise NotImplementedError, "How to implement this?"

#backwards compatibility
WModel = Model

class ListModel(Model):
    """
    I wrap a Python list and allow it to interact with the Woven
    models and submodels.
    """
    __implements__ = interfaces.IModel
    
    parent = None
    name = None
    def __init__(self, orig):
        self.orig = orig

    def getSubmodel(self, name):
        orig = self.orig
        return adaptToIModel(orig[int(name)], self, name)
    
    def setSubmodel(self, name, value):
        self.orig[int(name)] = value

    def __getitem__(self, name):
        return self.getSubmodel(name)
    
    def __setitem__(self, name, value):
        self.setSubmodel(name, value)
    
    def getData(self):
        return self.orig
    
    def setData(self, data):
        setattr(self.parent, self.name, data)

    def __repr__(self):
        myLongName = reflect.qual(self.__class__)
        return "<%s instance at 0x%x: wrapped data: %s>" % (myLongName,
                                                            id(self), self.orig)

# pyPgSQL returns "PgResultSet" instances instead of lists, which look, act
# and breathe just like lists. pyPgSQL really shouldn't do this, but this works
try:
    from pyPgSQL import PgSQL
    components.registerAdapter(ListModel, PgSQL.PgResultSet, interfaces.IModel)
except:
    pass

class DictionaryModel(Model):
    """
    I wrap a Python dictionary and allow it to interact with the Woven
    models and submodels.
    """
    __implements__ = interfaces.IModel

    parent = None
    name = None
    def __init__(self, orig):
        self.orig = orig

    def getSubmodel(self, name):
        orig = self.orig
        return adaptToIModel(orig[name], self, name)

    def setSubmodel(self, name, value):
        self.orig[name] = value

    def getData(self):
        return self.orig

    def setData(self, data):
        setattr(self.parent, self.name, data)

    def __repr__(self):
        myLongName = reflect.qual(self.__class__)
        return "<%s instance at 0x%x: wrapped data: %s>" % (myLongName,
                                                            id(self), self.orig)

class Wrapper(Model):
    """
    I'm a generic wrapper to provide limited interaction with the
    Woven models and submodels.
    """
    __implements__ = interfaces.IModel
    
    parent = None
    name = None
    def __init__(self, orig):
        Model.__init__(self)
        self.orig = orig

    def getData(self):
        return self.orig
    
    def setData(self, data):
        if self.parent:
            self.parent.setSubmodel(self.name, data)
        self.orig = data

    def __repr__(self):
        myLongName = reflect.qual(self.__class__)
        return "<%s instance at 0x%x: wrapped data: %s>" % (myLongName,
                                                            id(self), self.orig)

class AttributeWrapper(Wrapper):
    """
    I wrap an attribute named "name" of the given parent object.
    """
    def __init__(self, parent, name):
        self.orig = None
        parent = ObjectWrapper(parent)
        Wrapper.__init__(self, parent.getSubmodel(name))
        self.parent = parent
        self.name = name


class ObjectWrapper(Wrapper):
    """
    I may wrap an object and allow it to interact with the Woven models
    and submodels.  By default, I am not registered for use with anything.
    """
    __implements__ = interfaces.IModel

    parent = None
    name = None
    def getSubmodel(self, name):
        return adaptToIModel(getattr(self.orig, name), self, name)

    def setSubmodel(self, name, value):
        setattr(self.orig, name, value)

class UnsafeObjectWrapper(ObjectWrapper):
    """
    I may wrap an object and allow it to interact with the Woven models
    and submodels.  By default, I am not registered for use with anything.
    I am unsafe because I allow methods to be called. In fact, I am
    dangerously unsafe.  Be wary or I will kill your security model!
    """
    __implements__ = interfaces.IModel

    parent = None
    name = None
    def getSubmodel(self, name):
        value = getattr(self.orig, name)
        if callable(value):
            return value()
        return adaptToIModel(value, self, name)

from twisted.internet import defer

try:
    components.registerAdapter(ListModel, types.ListType, interfaces.IModel)
    components.registerAdapter(DictionaryModel, types.DictionaryType, interfaces.IModel)
    components.registerAdapter(Wrapper, types.StringType, interfaces.IModel)
    components.registerAdapter(ListModel, types.TupleType, interfaces.IModel)
    components.registerAdapter(Wrapper, defer.Deferred, interfaces.IModel)
except ValueError:
    # The adapters were already registered
    pass

