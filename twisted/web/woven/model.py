
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

import types

from twisted.python import components, mvc, reflect


WModel = mvc.Model


class ListModel:
    """
    I wrap a Python list and allow it to interact with the Woven
    models and submodels.
    """
    __implements__ = mvc.IModel
    
    parent = None
    name = None
    def __init__(self, orig):
        self.orig = orig

    def getSubmodel(self, name):
        orig = self.orig
        return orig[int(name)]
    
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
    components.registerAdapter(ListModel, PgSQL.PgResultSet, mvc.IModel)
except:
    pass

class DictionaryModel:
    """
    I wrap a Python dictionary and allow it to interact with the Woven
    models and submodels.
    """
    __implements__ = mvc.IModel

    parent = None
    name = None
    def __init__(self, orig):
        self.orig = orig

    def getSubmodel(self, name):
        orig = self.orig
        return self.orig[name]

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

class Wrapper:
    """
    I'm a generic wrapper to provide limited interaction with the
    Woven models and submodels.
    """
    __implements__ = mvc.IModel
    
    parent = None
    name = None
    def __init__(self, orig):
        self.orig = orig

    def getSubmodel(self, name):
        raise NotImplementedError
    
    def setSubmodel(self, name, value):
        raise NotImplementedError

    def getData(self):
        return self.orig
    
    def setData(self, data):
        self.parent.setSubmodel(self.name, data)

    def __repr__(self):
        myLongName = reflect.qual(self.__class__)
        return "<%s instance at 0x%x: wrapped data: %s>" % (myLongName,
                                                            id(self), self.orig)

from twisted.internet import defer

try:
    components.registerAdapter(ListModel, types.ListType, mvc.IModel)
    components.registerAdapter(DictionaryModel, types.DictionaryType, mvc.IModel)
    components.registerAdapter(Wrapper, types.StringType, mvc.IModel)
    components.registerAdapter(Wrapper, types.TupleType, mvc.IModel)
    components.registerAdapter(Wrapper, defer.Deferred, mvc.IModel)
except ValueError:
    # The adapters were already registered
    pass

