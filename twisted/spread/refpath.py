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

Path-based references for PB, and other reference-based protocols.

Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}

Stability: semi-stable

Future Plans: None at this point besides a final overview and finalization
pass.

"""


from twisted.python import log

from flavors import Referenceable, Viewable
from copy import copy
import os



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
    def __init__(self, request, path):
        self.request = request
        self.root = request.site.resource
        self.path = path
        # Make sure we have our own copy of these lists,
        # so they can be mutated.
        self.prepath = []
        self.postpath = copy(path)

    def __getattr__(self, name):
        """
        We need to delegate any methods which we don't override
        to the real request object that got passed to us.
        """
        return getattr(self.request, name)
    
    def _lookup(self, name, acquire=0, debug=0):
        if debug: log.msg("Looking for %s" % name)
        obRef = self
        ob = self.getObject()
        while obRef:
            if debug: log.msg(obRef)
            if acquire and hasattr(ob, name):
                return getattr(ob, name)
            elif hasattr(ob, 'listNames'):
                names = ob.listNames()
                if debug: log.msg('%s %s %s' % (name, names, name in names))
                if name in names:
                    if acquire:
                        return ob.getChild(name, self)
                    else:
                        foundPath = copy(obRef.path)
                        foundPath.append(name)
                        return PathReferenceAcquisitionContext(self.request, foundPath)

            # When the loop gets to the top of the containment heirarchy,
            # obRef will be set to None.
            # Then the loop will exit into the else.
            if obRef.path:
                obRef = obRef.parentRef()
                ob = obRef.getObject()
            else:
                obRef = None
        else:
            raise AttributeError, "%s not found." % name

    def getIndex(self):
        """
        Dereference this path reference object, then look for an object
        named 'index' inside of it and return it.
        """
        thisOb = self.getObject()
        if hasattr(self.root, 'indexNames'):
            indexNames = self.root.indexNames
        else:
            indexNames = ['index']
        
        childNames = thisOb.listNames()
        for indexName in indexNames:
            if indexName in childNames:
                return thisOb.getChild(indexName, self)

    def parentRef(self):
        """
        Return a reference to my parent.
        """
        return PathReferenceAcquisitionContext(self.request, self.path[:-1])

    def childRef(self, name):
        """
        Return a reference to the named child.
        """
        newPath = copy(self.path)
        newPath.append(name)
        return PathReferenceAcquisitionContext(self.request, newPath)

    def siblingRef(self, name):
        """
        Return a reference to a sibling of mine.
        """
        newPath = copy(self.path)
        newPath[-1] = name
        return PathReferenceAcquisitionContext(self.request, newPath)

    def diskPath(self):
        """
        Return the path to me on disk.
        """
        self.getObject()
        pathList = [self.root.path]
        log.msg("PathReferenceAcquisitionContext.path:", self.path)
        pathList.extend(self.path)
        return apply(os.path.join, pathList)

    def relativePath(self, request):
        """
        Return the URL to the resource, relative to the current request object
        """
        log.msg(self.path, request.prepath)
        relPath = copy(self.path)
        for segNum in range(len(request.prepath)):
            if relPath[0] == request.prepath[segNum]:
                relPath.pop(0)
            else:
                upNum = len(request.prepath) - segNum
                break
        upPath = ['..'] * (upNum - 1)
        upPath.insert(0, '.')
        upPath.extend(relPath)
        return "/".join(upPath)

    def locate(self, name, debug=0):
        """
        Get a reference to an object with the given name which is somewhere
        on the path above us.
        """
        return self._lookup(name, debug=debug)

    def acquire(self, name, debug=0):
        """
        Look for an attribute or element by name in all of our parents
        """
        return self._lookup(name, acquire=1, debug=debug)

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
