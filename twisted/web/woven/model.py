
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

from twisted.python import components, mvc


WModel = mvc.Model


class ListModel:
    __implements__ = mvc.IModel
    
    parent = None
    name = None
    def __init__(self, orig):
        self.orig = orig

    def getSubmodel(self, name):
        return self.orig[int(name)]
    
    def setSubmodel(self, name, value):
        self.orig[int(name)] = value

    def getData(self):
        return self.orig
    
    def setData(self, data):
        setattr(self.parent, self.name, data)


# pyPgSQL returns "PgResultSet" instances instead of lists, which look, act
# and breathe just like lists. pyPgSQL really shouldn't do this, but this works
try:
    from pyPgSQL import PgSQL
    components.registerAdapter(ListModel, PgSQL.PgResultSet, mvc.IModel)
except:
    pass


class Wrapper:
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


from twisted.internet import defer

try:
    components.registerAdapter(ListModel, types.ListType, mvc.IModel)
    components.registerAdapter(Wrapper, types.StringType, mvc.IModel)
    components.registerAdapter(Wrapper, types.TupleType, mvc.IModel)
    components.registerAdapter(Wrapper, defer.Deferred, mvc.IModel)
except ValueError:
    # The adapters were already registered
    pass

