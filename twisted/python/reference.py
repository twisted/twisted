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
        global callList
        try:
            callList
        except:
            print 'wha??'
            callList = []
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
    """Resolver(reflist,lookup)
    
    reflist: a list of Reference objects.
    
    lookup: is an object which responds to the __getitem__ interface
    and contains all the keys referred to by the References in
    *reflist*.
    
    Traverse a (relatively -- I am not 100% sure there are no
    limitations) arbitrary graph of objects and setattr()/setitem[]=
    your way around them, to resolve all References.
    """

    def __init__(self,lookup):
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
        """Resolver.resolve(reflist) -> reflist
        
        reflist: a list of objects which may contain Reference
        objects, which can be resolved by looking in self.lookup
        """
        global callList
        try:
            for x in reflist:
                self.res(x)
            for call in callList:
                name, method, args, kw = call
                instance = self[name]
                funcall = getattr(instance, method)
                apply(funcall, args, kw)
                
            return reflist
        finally:
            callList = []
            del self.__done


def _test():
    _=Reference
    class A: pass
    a=A()
    a.m=_('x')
    a.n=_('y')
    a.o=_('z')
    
    x=[1,2,_('x')]
    y=[_('x'),_('y'),_('z')]
    z={'a':1,'b':2,'x':_('x'),'y':_('y')}
    look={'x':x,
          'y':y,
          'z':z}
    Resolver(look).resolve([a,x,y,z])
    assert x[2]==x
    assert y==[x,y,z], y
    assert z['x']==x
    assert z['y']==y
    assert a.m==x
    assert a.n==y
    assert a.o==z

if __name__=='__main__':
    _test()
        
