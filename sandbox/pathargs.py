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

from twisted.web.resource import Resource
class PathArgs(Resource):
    """ Provides a mechanism to add 'pathargs' attribute to
        each request, and to populate it with instances of
        key:value pairs found in child paths.  The value for
        each key will be an array, optionally split further
        with a comma.
    """
    def __init__(self,eat=[]):
        Resource.__init__(self)
        self.eat = eat
    def getChild(self,path,request):
        pair = path.split(':')
        if 2 == len(pair):
            (key,val) = pair
            lst = request.pathargs.get(key,[])
            if not lst: request.pathargs[key] = lst
            lst.append(val)
            return self
        for x in self.eat:
            if x == path:
                request.root += "%s/" % path
                return self
        return Resource.getChild(self,path,request)
    def getChildWithDefault(self,path,request):
        if not(hasattr(request,'root')):
            request.root = "/"
        if not(hasattr(request,'pathargs')):
            request.pathargs = {}
        return Resource.getChildWithDefault(self,path,request)

def test():
    from twisted.internet import reactor
    from twisted.web.server import Site
    from twisted.web.static import File

    class DynamicRequest(Resource):
        def isLeaf(self):
            return true
        def render(self, req):
            req.setHeader('Content-type','text/plain')
            resp = 'uri: %s \nargs: %s\npathargs: %s\n'
            return resp % ( req.uri, req.args, req.pathargs )

    root = PathArgs()
    root.putChild('dynamic', DynamicRequest())
    root.putChild('static',File('.'))
    site = Site(root)
    reactor.listenTCP(8080,site)
    reactor.run()

if '__main__' == __name__:
    test()
