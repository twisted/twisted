
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
twisted.reference: Latently resolveable references for streams
which have forward-references.
"""

from types import InstanceType, DictType, ListType


# This attribute makes this module non-thread-safe.  Sorry.
callList = []

class Deferred:
    def __init__(self, reference, methodName):
        self.methodName = methodName
        self.reference = reference
        
    def method(self, *args, **kw):
        self.reference.addCall(self.methodName, args, kw)

class Reference:
    def __init__(self, name):
        self.__name = name

    def addCall(self, method, args, kw):
        callList.append((self.__name, method, args, kw))

    def __cmp__(self, other):
        cmp(hash(self),hash(other))

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return "<Reference %s>" % repr(self.__name)

    __str__ = __repr__
    
    # Hasattr always returns true, and this crashes pickle.
    nonAttribs = ['__getinitargs__']

    def __getattr__(self, methodName):
        if methodName in self.nonAttribs:
            raise AttributeError(methodName)
        return Deferred(self, methodName).method

    def resolve(self, reality):
        result = reality[self.__name]
        return result

class AttributeReference(Reference):
    def __init__(self, name, attr):
        Reference.__init__(self,name)
        self.__attr=attr
        
    def resolve(self,reality):
        x = Reference.resolve(self,reality)
        result = getattr(x,self.__attr)
        return result
    
class Resolver:
    """I am can resolve backward named references in a block of code.

    Objects created by a block of code that are inserted into a dictionary I
    store a reference to may later indicate a backreference to one of those
    objects by creating a 'reference.Reference', specifying the key to be
    looked up later.

    Instantiate me with a lookup table populated with references, then resolve
    a graph of objects using that table.
    """

    def __init__(self,lookup):
        """Resolver(lookup)
        Create a resolver.
        
        @param lookup: is an object which responds to the C{__getitem__}
            interface and contains all the keys which can be referred to by
            the L{Reference}s in the C{'reflist'} argument to my L{'resolve'}
            method.
        
        """
        self.lookup=lookup
        self.__done={}
    
    def resdict(self,dict):
        "Resolve a dictionary; private use"
        for key,val in dict.items():
            if isinstance(val, Reference):
                resolved = val.resolve(self.lookup)
                dict[key] = resolved
            else:
                self.res(val)

    def resinst(self,inst):
        "Resolve an instance; private use"
        if (hasattr(inst,'__setitem__')
            and hasattr(inst,'__getitem__')):
            self.resdict(inst)
        for key, val in inst.__dict__.items():
            val = getattr(inst,key)
            if isinstance(val, Reference):
                # for those of you with reflect.Accessor derived
                # accessor methods, this will make sure that there is
                # no left-over state.
                del inst.__dict__[key]
                setattr(inst,key,val.resolve(self.lookup))
            else:
                self.res(val)
                
    def reslist(self,lst):
        "Resolve a list; private use"
        for x in xrange(len(lst)):
            val=lst[x]
            if isinstance(val,Reference):
                lst[x]=val.resolve(self.lookup)
            else: self.res(lst[x])
                
    def res(self,obj):
        "Traverse a single object's graph and resolve it and its subobjects."
        try:
            action={InstanceType:self.resinst,
                    DictType:self.resdict,
                    ListType:self.reslist}[type(obj)]
        except KeyError:
            pass
        else:
            i=id(obj)
            if self.__done.has_key(i): return
            self.__done[i]=obj
            action(obj)

        # erm, please don't put references into tuples... that would
        # make my life more difficult

    def resolve(self,reflist):
        """Resolve a list of references.

        @type reflist: C{List}
        @param reflist: A list of objects which may contain L{Reference}
            objects, which can be resolved by looking in C{self.lookup}.
        """
        global callList
        try:
            for x in reflist:
                self.res(x)
            for call in callList:
                name, method, args, kw = call
                instance = self.lookup[name]
                funcall = getattr(instance, method)
                apply(funcall, args, kw)
        finally:
            callList = []
            del self.__done
