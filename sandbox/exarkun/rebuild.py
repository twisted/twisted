# -*- coding: Latin-1 -*-

from twisted.python import components

class IRebuildable(components.Interface):
    def rebuild(self):
        """Build a new copy of this object and return it.
        """

def rebuild(obj):
    return IRebuildable(obj).rebuild()

def ImmutableObjectAdapter(original):
    return original

class _foo:
    pass

def ClassicClassAdapter(original):
    d = original.__dict__.copy()
    for k in d.keys():
        d[k] = IRebuildable(d[k]).rebuild()
    f = _foo()
    f.__class__ = reflect.namedAny(reflect.qual(original.__class__))
    f.__dict__ = d
    return f
