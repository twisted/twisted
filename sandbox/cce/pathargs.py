#
# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General
# Public License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307
# USA
#

from UserDict import UserDict
from twisted.python import components
from twisted.web import server
from twisted.web.resource import Resource


class IPathArgs(components.Interface):
    """Provide a dictionary object which contains arguments
    which were specified in pathargs format; pathargs format
    is /foo=bar/ where foo is the key and bar is the value.
    """

class odict(UserDict):
    def __init__(self):
        UserDict.__init__(self)
        self._keys = []
    def __setitem__(self, key, item):
        UserDict.__setitem__(self, key, item)
        if not key in self._keys:
            self._keys.append(key)
    def keys(self): 
        return self._keys

# Use a dict as the IPathArgs implementor for any given request
components.registerAdapter(lambda request: odict(), server.Request, IPathArgs)

class PathArgs(Resource):
    """ Provides a mechanism to add 'pathargs' attribute to
        each request, and to populate it with instances of
        key=value pairs found in child paths.  The value for
        each key will be an array, optionally split further
        with a comma.
    """
    def getChildPathArgs(self,path,request):
        pair = path.split('=')
        if 2 == len(pair):
            (key,val) = pair
            pathargs = IPathArgs(request)
            pathargs.setdefault(key, []).append(val)
            return self
    def getChild(self,path,request):
        ret = self.getChildPathArgs(path,request)
        if not ret: 
            ret = Resource.getChild(self,path,request)
        return ret 

def test():
    from twisted.internet import reactor
    from twisted.web.server import Site
    from twisted.web.static import File

    class DynamicRequest(Resource):
        def isLeaf(self):
            return true
        def render(self, req):
            pathargs = IPathArgs(req)
            req.setHeader('Content-type','text/html')
            resp = """
                <html><body><pre>uri: %s \nargs: %s\npathargs: %s
                </pre></body></html>
            """
            return resp % ( req.uri, req.args, pathargs )

    root = PathArgs()
    root.putChild('dynamic', DynamicRequest())
    root.putChild('static',File('.'))
    site = Site(root)
    reactor.listenTCP(8080,site)
    reactor.run()

if '__main__' == __name__:
    import sys               
    from twisted.python import log 
    log.startLogging(sys.stdout, 0) 
    test()
