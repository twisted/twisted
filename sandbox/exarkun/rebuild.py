# -*- test-case-name: test_rebuild -*-

from twisted.python import components

class IRebuildable(components.Interface):
    def rebuild(self, memo):
        """Build a new copy of this object and return it.
        """

def latest(klass):
    return reflect.namedAny(reflect.qual(klass))

def rebuild(obj):
    return IRebuildable(obj).rebuild({})

def ImmutableObjectAdapter(original, memo):
    return original

class ListAdapter(components.Adapter):
    def rebuild(self, memo):
        if id(original) in memo:
            return memo[id(original)]
        r = [IRebuildable(e).rebuild(memo) for e in original]
        memo[id(original)] = r
        return r

class _foo:
    pass
    
class _Cache(components.Adapter):
    def cret(self, memo, original, result):
        memo[id(original)] = result
        return result

class ClassicClassAdapter(_Cache):
    def rebuild(self, memo):
        if id(original) in memo:
            return memo[id(original)]
        d = original.__dict__.copy()
        for k in d.keys():
            d[k] = IRebuildable(d[k]).rebuild(memo)
        f = _foo()
        f.__class__ = latest(original.__class__)
        f.__dict__ = d
        return self.cret(memo, original, f)

class BoundMethodAdapter(_Cache):
    def rebuild(self, memo):
        if id(original) in memo:
            return memo[id(original)]
        klass = latest(original.im_class)
        self = original.im_self
        name = original.im_func.func_name
        return self.cret(memo, original, getattr(IRebuildable(self).rebuild(memo), name))

class UnboundMethodAdapter(_Cache):
    def rebuild(self, memo):
        if id(original) in memo:
            return memo[id(original)]
        klass = latest(original.im_class)
        name = original.im_func.func_name
        return self.cret(memo, original, getattr(latest, name))
