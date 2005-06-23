raise ImportError("FIXME: this file probably doesn't work.")
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I contain PythonScript, which is a very simple python script resource.
"""

import server
import resource
import error

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from twisted.web2 import http
from twisted import copyright
import traceback
import os
from twisted.web2 import resource
from twisted.web2 import static

rpyNoResource = """<p>You forgot to assign to the variable "resource" in your script. For example:</p>
<pre>
# MyCoolWebApp.rpy

import mygreatresource

resource = mygreatresource.MyGreatResource()
</pre>
"""

class AlreadyCached(Exception):
    """This exception is raised when a path has already been cached.
    """

class CacheScanner:
    def __init__(self, path, registry):
        self.path = path
        self.registry = registry
        self.doCache = 0

    def cache(self):
        c = self.registry.getCachedPath(self.path)
        if c is not None:
            raise AlreadyCached(c)
        self.recache()

    def recache(self):
        self.doCache = 1

noRsrc = error.ErrorPage(500, "Whoops! Internal Error", rpyNoResource)

def ResourceScript(path, registry):
    """
    I am a normal py file which must define a 'resource' global, which should
    be an instance of (a subclass of) web.resource.Resource; it will be
    renderred.
    """
    cs = CacheScanner(path, registry)
    glob = {'__file__': path,
            'resource': noRsrc,
            'registry': registry,
            'cache': cs.cache,
            'recache': cs.recache}
    try:
        execfile(path, glob, glob)
    except AlreadyCached, ac:
        return ac.args[0]
    rsrc = glob['resource']
    if cs.doCache and rsrc is not noRsrc:
        registry.cachePath(path, rsrc)
    return rsrc

def ResourceTemplate(path, registry):
    from quixote import ptl_compile

    glob = {'__file__': path,
            'resource': error.ErrorPage(500, "Whoops! Internal Error",
                                        rpyNoResource),
            'registry': registry}

    e = ptl_compile.compile_template(open(path), path)
    exec e in glob
    return glob['resource']


class ResourceScriptWrapper(resource.Resource):

    def __init__(self, path, registry=None):
        resource.Resource.__init__(self)
        self.path = path
        self.registry = registry or static.Registry()

    def render(self, request):
        res = ResourceScript(self.path, self.registry)
        return res.render(request)

    def getChildWithDefault(self, path, request):
        res = ResourceScript(self.path, self.registry)
        return res.getChildWithDefault(path, request)



class ResourceScriptDirectory(resource.Resource):
    def __init__(self, pathname, registry=None):
        resource.Resource.__init__(self)
        self.path = pathname
        self.registry = registry or static.Registry()

    def getChild(self, path, request):
        fn = os.path.join(self.path, path)

        if os.path.isdir(fn):
            return ResourceScriptDirectory(fn, self.registry)
        if os.path.exists(fn):
            return ResourceScript(fn, self.registry)
        return error.NoResource()

    def render(self, request):
        return error.NoResource().render(request)


