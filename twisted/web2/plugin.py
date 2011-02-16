# -*- test-case-name: twisted.web2.test.test_plugin -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""I'm a set of utility functions and resources for using twisted.plugins
to locate resources.

Example Usage:
root.putChild('test', resourcePlugger('TestResource'))
"""

from twisted.web2 import resource, http, iweb
from twisted.plugin import getPlugins
from twisted.python.reflect import namedClass

class PluginResource(resource.Resource):
    def __init__(self, *args, **kwargs):
        """A plugin resource atleast has to accept any arguments given to it,
        but it doesn't have to do anything with it, this is dumb I know.
        """
        pass


class TestResource(PluginResource, resource.LeafResource):
    def __init__(self, foo=None, bar=None):
        self.foo = foo
        self.bar = bar

    def locateChild(self, req, segments):
        return resource.LeafResource.locateChild(self, req, segments)

    def render(self, req):
        return http.Response(200, stream="I am a very simple resource, a pluggable resource too")


class NoPlugin(resource.LeafResource):
    def __init__(self, plugin):
        self.plugin = plugin
        
    def render(self, req):
        return http.Response(404, stream="No Such Plugin %s" % self.plugin)


def resourcePlugger(name, *args, **kwargs):
    resrcClass = None

    for p in getPlugins(iweb.IResource):
        if p.name == name:
            resrcClass = namedClass(p.className)
            break

    if resrcClass is None:
        resrcClass = kwargs.get('defaultResource', None)
        if resrcClass is None:
            return NoPlugin(name)
        
        del kwargs['defaultResource']

    return resrcClass(*args, **kwargs)
