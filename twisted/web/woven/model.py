# -*- test-case-name: twisted.web.test.test_woven -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


__version__ = "$Revision: 1.53 $"[11:-2]

import types
import weakref
import warnings

from zope.interface import implements

from twisted.python import components, reflect
from twisted.internet import defer

from twisted.web.woven import interfaces

class _Nothing: pass

def adaptToIModel(m, parent=None, submodel=None):
    adapted = interfaces.IModel(m, None)
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
    implements(interfaces.IModel)

    def __init__(self, *args, **kwargs):
        if len(args):
            self.original = args[0]
        else:
            self.original = self
        self.name = ''
        self.parent = None
        self.views = []
        self.subviews = {}
        self.submodels = {}
        self._getter = kwargs.get('getter')
        self._setter = kwargs.get('setter')
        self.cachedFor = None
        self.initialize(*args, **kwargs)

    def __getstate__(self):
        self.views = []
        self.subviews = {}
        self.submodels = {}
        return self.__dict__

    def invalidateCache(self):
        """Invalidate the cache for this object, so the next time
        getData is called, it's getter method is called again.
        """
        self.cachedFor = None

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
        if view not in [ref() for ref in self.views]:
            self.views.append(weakref.ref(view))

    def addSubview(self, name, subview):
        subviewList = self.subviews.get(name, [])
        subviewList.append(weakref.ref(subview))
        self.subviews[name] = subviewList

    def removeView(self, view):
        """
        Remove a view that the model no longer should keep track of.
        """
        # AM: loop on a _copy_ of the list, since we're changing it!!!
        for weakref in list(self.views):
            ref = weakref()
            if ref is view or ref is None:
                self.views.remove(weakref)

    def setGetter(self, getter):
        self._getter = getter

    def setSetter(self, setter):
        self._setter = setter

    def notify(self, changed=None):
        """
        Notify all views that something was changed on me.
        Passing a dictionary of {'attribute': 'new value'} in changed
        will pass this dictionary to the view for increased performance.
        If you don't want to do this, don't, and just use the traditional
        MVC paradigm of querying the model for things you're interested
        in.
        """
        self.cachedFor = None
        if changed is None: changed = {}
        retVal = []
        # AM: loop on a _copy_ of the list, since we're changing it!!!
        for view in list(self.views):
            ref = view()
            if ref is not None:
                retVal.append((ref, ref.modelChanged(changed)))
            else:
                self.views.remove(view)
        for key, value in self.subviews.items():
            if value.wantsAllNotifications or changed.has_key(key):
                for item in list(value):
                    ref = item()
                    if ref is not None:
                        retVal.append((ref, ref.modelChanged(changed)))
                    else:
                        value.remove(item)
        return retVal

    protected_names = ['initialize', 'addView', 'addSubview', 'removeView', 'notify', 'getSubmodel', 'setSubmodel', 'getData', 'setData']
    allowed_names = []

    def lookupSubmodel(self, request, submodelName):
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
            return None

        # Special case: If the first character is /
        # Start at the bottom of the model stack
        currentModel = self
        if submodelName[0] == '/':
            while currentModel.parent is not None:
                currentModel = currentModel.parent
            submodelName = submodelName[1:]

        submodelList = submodelName.split('/')  #[:-1]
#         print "submodelList", submodelList
        for element in submodelList:
            if element == '.' or element == '':
                continue
            elif element == '..':
                currentModel = currentModel.parent
            else:
                currentModel = currentModel.getSubmodel(request, element)
                if currentModel is None:
                    return None
        return currentModel

    def submodelCheck(self, request, name):
        """Check if a submodel name is allowed.  Subclass me to implement a
        name security policy.
        """
        if self.allowed_names:
            return (name in self.allowed_names)
        else:
            return (name and name[0] != '_' and name not in self.protected_names)


    def submodelFactory(self, request, name):
        warnings.warn("Warning: default Model lookup strategy is changing:"
                      "use either AttributeModel or MethodModel for now.",
                      DeprecationWarning)
        if hasattr(self, name):
            return getattr(self, name)
        else:
            return None

    def getSubmodel(self, request, name):
        """
        Get the submodel `name' of this model. If I ever return a
        Deferred, then I ought to check for cached values (created by
        L{setSubmodel}) before doing a regular Deferred lookup.
        """
        if self.submodels.has_key(name):
            return self.submodels[name]
        if not self.submodelCheck(request, name):
            return None
        m = self.submodelFactory(request, name)
        if m is None:
            return None
        sm = adaptToIModel(m, self, name)
        self.submodels[name] = sm
        return sm

    def setSubmodel(self, request=None, name=None, value=None):
        """
        Set a submodel on this model. If getSubmodel or lookupSubmodel
        ever return a Deferred, I ought to set this in a place that
        lookupSubmodel/getSubmodel know about, so they can use it as a
        cache.
        """
        if self.submodelCheck(request, name):
            if self.submodels.has_key(name):
                del self.submodels[name]
            setattr(self, name, value)

    def dataWillChange(self):
        pass

    def getData(self, request):
        if self.cachedFor != id(request) and self._getter is not None:
            self.cachedFor = id(request)
            self.dataWillChange()
            self.orig = self.original = self._getter(request)
        return self.original

    def setData(self, request, data):
        if self._setter is not None:
            self.cachedFor = None
            return self._setter(request, data)
        else:
            if hasattr(self, 'parent') and self.parent:
                self.parent.setSubmodel(request, self.name, data)
            self.orig = self.original = data


class MethodModel(Model):
    """Look up submodels with wmfactory_* methods.
    """

    def submodelCheck(self, request, name):
        """Allow any submodel for which I have a submodel.
        """
        return hasattr(self, "wmfactory_"+name)

    def submodelFactory(self, request, name):
        """Call a wmfactory_name method on this model.
        """
        meth = getattr(self, "wmfactory_"+name)
        return meth(request)
    
    def getSubmodel(self, request=None, name=None):
        if name is None:
            warnings.warn("Warning! getSubmodel should now take the request as the first argument")
            name = request
            request = None

        cached = self.submodels.has_key(name)
        sm = Model.getSubmodel(self, request, name)
        if sm is not None:
            if not cached:
                sm.cachedFor = id(request)
            sm._getter = getattr(self, "wmfactory_"+name)
        return sm


class AttributeModel(Model):
    """Look up submodels as attributes with hosts.allow/deny-style security.
    """
    def submodelFactory(self, request, name):
        if hasattr(self, name):
            return getattr(self, name)
        else:
            return None


#backwards compatibility
WModel = Model


class Wrapper(Model):
    """
    I'm a generic wrapper to provide limited interaction with the
    Woven models and submodels.
    """
    parent = None
    name = None
    def __init__(self, orig):
        Model.__init__(self)
        self.orig = self.original = orig

    def dataWillChange(self):
        pass

    def __repr__(self):
        myLongName = reflect.qual(self.__class__)
        return "<%s instance at 0x%x: wrapped data: %s>" % (myLongName,
                                                            id(self), self.original)


class ListModel(Wrapper):
    """
    I wrap a Python list and allow it to interact with the Woven
    models and submodels.
    """
    def dataWillChange(self):
        self.submodels = {}

    def getSubmodel(self, request=None, name=None):
        if name is None and type(request) is type(""):
            warnings.warn("Warning!")
            name = request
            request = None
        if self.submodels.has_key(name):
            return self.submodels[name]
        orig = self.original
        try:
            i = int(name)
        except:
            return None
        if i > len(orig):
            return None
        sm = adaptToIModel(orig[i], self, name)
        self.submodels[name] = sm
        return sm

    def setSubmodel(self, request=None, name=None, value=None):
        if value is None:
            warnings.warn("Warning!")
            value = name
            name = request
            request = None
        self.original[int(name)] = value

    def __len__(self):
        return len(self.original)

    def __getitem__(self, name):
        return self.getSubmodel(None, str(name))

    def __setitem__(self, name, value):
        self.setSubmodel(None, str(name), value)

    def __repr__(self):
        myLongName = reflect.qual(self.__class__)
        return "<%s instance at 0x%x: wrapped data: %s>" % (myLongName,
                                                            id(self), self.original)


class StringModel(ListModel):

    """ I wrap a Python string and allow it to interact with the Woven models
    and submodels.  """

    def setSubmodel(self, request=None, name=None, value=None):
        raise ValueError("Strings are immutable.")


# pyPgSQL returns "PgResultSet" instances instead of lists, which look, act
# and breathe just like lists. pyPgSQL really shouldn't do this, but this works
try:
    from pyPgSQL import PgSQL
    components.registerAdapter(ListModel, PgSQL.PgResultSet, interfaces.IModel)
except:
    pass

class DictionaryModel(Wrapper):
    """
    I wrap a Python dictionary and allow it to interact with the Woven
    models and submodels.
    """
    def dataWillChange(self):
        self.submodels = {}

    def getSubmodel(self, request=None, name=None):
        if name is None and type(request) is type(""):
            warnings.warn("getSubmodel must get a request argument now")
            name = request
            request = None
        if self.submodels.has_key(name):
            return self.submodels[name]
        orig = self.original
        if name not in orig:
            return None
        sm = adaptToIModel(orig[name], self, name)
        self.submodels[name] = sm
        return sm

    def setSubmodel(self, request=None, name=None, value=None):
        if value is None:
            warnings.warn("Warning!")
            value = name
            name = request
            request = None
        self.original[name] = value


class AttributeWrapper(Wrapper):
    """
    I wrap an attribute named "name" of the given parent object.
    """
    def __init__(self, parent, name):
        self.original = None
        parent = ObjectWrapper(parent)
        Wrapper.__init__(self, parent.getSubmodel(None, name))
        self.parent = parent
        self.name = name


class ObjectWrapper(Wrapper):
    """
    I may wrap an object and allow it to interact with the Woven models
    and submodels.  By default, I am not registered for use with anything.
    """
    def getSubmodel(self, request=None, name=None):
        if name is None and type(request) is type(""):
            warnings.warn("Warning!")
            name = request
            request = None
        if self.submodels.has_key(name):
            return self.submodels[name]
        sm = adaptToIModel(getattr(self.original, name), self, name)
        self.submodels[name] = sm
        return sm

    def setSubmodel(self, request=None, name=None, value=None):
        if value is None:
            warnings.warn("Warning!")
            value = name
            name = request
            request = None
        setattr(self.original, name, value)

class UnsafeObjectWrapper(ObjectWrapper):
    """
    I may wrap an object and allow it to interact with the Woven models
    and submodels.  By default, I am not registered for use with anything.
    I am unsafe because I allow methods to be called. In fact, I am
    dangerously unsafe.  Be wary or I will kill your security model!
    """
    def getSubmodel(self, request=None, name=None):
        if name is None and type(request) is type(""):
            warnings.warn("Warning!")
            name = request
            request = None
        if self.submodels.has_key(name):
            return self.submodels[name]
        value = getattr(self.original, name)
        if callable(value):
            return value()
        sm = adaptToIModel(value, self, name)
        self.submodels = sm
        return sm


class DeferredWrapper(Wrapper):
    def setData(self, request=None, data=_Nothing):
        if data is _Nothing:
            warnings.warn("setData should be called with request as first arg")
            data = request
            request = None
        if isinstance(data, defer.Deferred):
            self.original = data
        else:
            views, subviews = self.views, self.subviews
            new = adaptToIModel(data, self.parent, self.name)
            self.__class__ = new.__class__
            self.__dict__ = new.__dict__
            self.views, self.subviews = views, subviews

class Link(AttributeModel):
    def __init__(self, href, text):
        AttributeModel.__init__(self)
        self.href = href
        self.text = text

try:
    components.registerAdapter(StringModel, types.StringType, interfaces.IModel)
    components.registerAdapter(ListModel, types.ListType, interfaces.IModel)
    components.registerAdapter(ListModel, types.TupleType, interfaces.IModel)
    components.registerAdapter(DictionaryModel, types.DictionaryType, interfaces.IModel)
    components.registerAdapter(DeferredWrapper, defer.Deferred, interfaces.IModel)
    components.registerAdapter(DeferredWrapper, defer.DeferredList, interfaces.IModel)
except ValueError:
    # The adapters were already registered
    pass
