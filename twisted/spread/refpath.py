# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Path-based references for PB, and other reference-based protocols.

Maintainer: Glyph Lefkowitz
"""


from copy import copy
import os, warnings

from twisted.python import log
from twisted.spread.flavors import Referenceable, Viewable

warnings.warn(
    "twisted.spread.refpath is deprecated since Twisted 9.0.",
    category=DeprecationWarning, stacklevel=2)

### "Server"-side objects

class PathReferenceContext:
    def __init__(self, path, root):
        self.metadata = {}
        self.path = path
        self.root = root

    def __setitem__(self, key, item):
        self.metadata[key] = item

    def __getitem__(self, key):
        return self.metadata[key]

    def getObject(self):
        o = self.root
        for p in self.path:
            o = o.getChild(p, self)
        return o

class PathReference:
    def __init__(self):
        self.children = {}
    def getChild(self, child, ctx):
        return self.children[child]

class PathReferenceDirectory(Referenceable):
    def __init__(self, root, prefix="remote"):
        self.root = root
        self.prefix = prefix
    def remote_callPath(self, path, name, *args, **kw):
        ctx = PathReferenceContext(path, self)
        obj = ctx.getObject()
        return apply(getattr(obj, "%s_%s" % (self.prefix, name)), args, kw)

class PathReferenceContextDirectory(Referenceable):
    def __init__(self, root, prefix="remote"):
        self.root = root
        self.prefix = prefix
    def remote_callPath(self, path, name, *args, **kw):
        ctx = PathReferenceContext(path, self)
        obj = ctx.getObject()
        return apply(getattr(obj, "%s_%s" % (self.prefix, name)),
                     (ctx,)+args, kw)

class PathViewDirectory(Viewable):
    def __init__(self, root, prefix="view"):
        self.root = root
        self.prefix = prefix
    def view_callPath(self, perspective, path, name, *args, **kw):
        ctx = PathReferenceContext(path, self)
        obj = ctx.getObject()
        return apply(getattr(obj, "%s_%s" % (self.prefix, name)),
                     (perspective,)+args, kw)

class PathViewContextDirectory(Viewable):
    def __init__(self, root, prefix="view"):
        self.root = root
        self.prefix = prefix
    def view_callPath(self, perspective, path, name, *args, **kw):
        ctx = PathReferenceContext(path, self)
        obj = ctx.getObject()
        return apply(getattr(obj, "%s_%s" % (self.prefix, name)),
                     (perspective,ctx)+args, kw)

### "Client"-side objects

class RemotePathReference:
    def __init__(self, ref, path):
        self.ref = ref
        self.path = path

    def callRemote(self, name, *args, **kw):
        apply(self.ref.callRemote,
              ("callPath", self.path, name)+args, kw)
