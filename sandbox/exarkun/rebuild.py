# -*- test-case-name: test_rebuild -*-

from twisted.python import components
from twisted.python import reflect

class IRebuildable(components.Interface):
    def rebuild(self, memo):
        """Build a new copy of this object and return it.
        """

def latest(klass):
    return reflect.namedAny(reflect.qual(klass))

def rebuild(obj):
    return IRebuildable(obj).rebuild({})

class ImmutableObjectAdapter(components.Adapter):
    def rebuild(self, memo):
        return self.original

class _foo:
    pass
    
class _Cache(components.Adapter):
    def cret(self, memo, original, result):
        memo[id(original)] = result
        return result

class ListAdapter(_Cache):
    def rebuild(self, memo):
        o = self.original
        if id(o) in memo:
            return memo[id(o)]
        return self.cret(memo, o, [IRebuildable(e).rebuild(memo) for e in o])

class DictAdapter(_Cache):
    def rebuild(self, memo):
        o = self.original
        if id(o) in memo:
            return memo[id(o)]
        d = {}
        for (k, v) in d.iteritems():
            d[IRebuildable(k).rebuild(memo)] = IRebuildable(v).rebuild(memo)
        return self.cret(memo, o, d)

class ClassicClassAdapter(_Cache):
    def rebuild(self, memo):
        o = self.original
        if id(o) in memo:
            return memo[id(o)]
        d = IRebuildable(o.__dict__).rebuild(memo)
        f = _foo()
        f.__class__ = latest(o.__class__)
        f.__dict__ = d
        return self.cret(memo, o, f)

class BoundMethodAdapter(_Cache):
    def rebuild(self, memo):
        o = self.original
        if id(o) in memo:
            return memo[id(o)]
        klass = latest(o.im_class)
        self = o.im_self
        name = o.im_func.func_name
        return self.cret(memo, o, getattr(IRebuildable(self).rebuild(memo), name))

class UnboundMethodAdapter(_Cache):
    def rebuild(self, memo):
        o = self.original
        if id(o) in memo:
            return memo[id(o)]
        klass = latest(o.im_class)
        name = o.im_func.func_name
        return self.cret(memo, o, getattr(latest, name))
