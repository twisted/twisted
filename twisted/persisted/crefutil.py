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
Utility classes for dealing with circular references.
"""

try:
    from new import instance
    from new import instancemethod
except:
    from org.python.core import PyMethod
    instancemethod = PyMethod


class NotKnown:
    def __init__(self):
        self.dependants = []

    def addDependant(self, mutableObject, key):
        self.dependants.append( (mutableObject, key) )

    def resolveDependants(self, newObject):
        for mut, key in self.dependants:
            mut[key] = newObject
            if isinstance(newObject, NotKnown):
                newObject.addDependant(mut, key)

    def __hash__(self):
        assert 0, "I am not to be used as a dictionary key."


class _Tuple(NotKnown):
    def __init__(self, l):
        NotKnown.__init__(self)
        self.l = l
        self.locs = []
        for idx in xrange(len(l)):
            if isinstance(l[idx], NotKnown):
                self.locs.append(idx)
                l[idx].addDependant(self, idx)

    def __setitem__(self, n, obj):
        self.l[n] = obj
        if not isinstance(obj, NotKnown):
            self.locs.remove(n)
            if not self.locs:
                self.resolveDependants(tuple(self.l))

class _InstanceMethod(NotKnown):
    def __init__(self, im_name, im_self, im_class):
        NotKnown.__init__(self)
        self.my_class = im_class
        self.name = im_name
        # im_self _must_ be a
        im_self.addDependant(self, 0)

    def __call__(self, *args, **kw):
        import traceback
        print 'instance method %s.%s' % (str(self.my_class), self.name)
        print 'being called with %r %r' % (args, kw)
        traceback.print_stack()
        assert 0

    def __setitem__(self, n, obj):
        assert n == 0, "only zero index allowed"
        if not isinstance(obj, NotKnown):
            self.resolveDependants(instancemethod(self.my_class.__dict__[self.name],
                                                  obj,
                                                  self.my_class))

class _DictKeyAndValue:
    def __init__(self, dict):
        self.dict = dict
    def __setitem__(self, n, obj):
        if n not in (1, 0):
            raise AssertionError("DictKeyAndValue should only ever be called with 0 or 1")
        if n: # value
            self.value = obj
        else:
            self.key = obj
        if hasattr(self, "key") and hasattr(self, "value"):
            self.dict[self.key] = self.value


class _Dereference(NotKnown):
    def __init__(self, id):
        NotKnown.__init__(self)
        self.id = id

