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

from flavors import Referenceable, Viewable
from copy import copy

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

class PathReferenceAcquisitionContext(PathReferenceContext):
    def __init__(self, path, root, parentRef):
        PathReferenceContext.__init__(self, path, root)
        self.metadata['parentRef'] = parentRef

    def _lookup(self, name, acquire=0):
        obRef = self
        ob = self.getObject()
        found = 0
        while not found:
            if acquire and hasattr(ob, name):
                retVal = getattr(ob, name)
                break
            elif hasattr(ob, 'listNames') and name in ob.listNames():
                if acquire:
                    retVal = ob.getChild(name)
                else:
                    foundPath = copy(obRef.path)
                    foundPath.append(name)
                    retVal = PathReferenceAcquisitionContext(foundPath,
                                                             obRef.root, obRef)
                break

            obRef = obRef['parentRef']
            ob = obRef.getObject()
        else:
            raise AttributeError, "%s not found." % name
        return retVal

    def locate(self, name):
        """
        Get a reference to an object with the given name which is somewhere
        on the path above us.
        """
        return self._lookup(name)

    def acquire(self, name):
        """
        Look for an attribute or element by name in all of our parents
        """
        return self._lookup(name, acquire=1)

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
