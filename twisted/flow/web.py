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
# Author: Clark Evans  (cce@clarkevans.com)

""" flow.web

    This contains wrappers to apply flow to components in twisted.web.*

"""
from controller import Deferred
from twisted.web import resource, server
from twisted.python.failure import Failure

class Resource(resource.Resource):
    """ a resource which uses flow in its page generation

            from __future__ import generators
            from twisted.flow import flow
            
            def render(req):
                req.write("<html><head><title>Delayed</title></head>")
                req.write("<body><h1>Delayed WebPage</h1>")
                yield flow.Cooperate(5)
                req.write("<p>Delayed Content</p></body></html>")
            
            if __name__=='__main__':
                from twisted.internet import reactor
                from twisted.web.server import Site
                from twisted.flow.web import Resource
                print "visit http://localhost:8081/ to view"
                reactor.listenTCP(8081,Site(Resource(render)))
                reactor.run()
    """
    def __init__(self, gen):
        resource.Resource.__init__(self)
        self.gen = gen
    def isLeaf(self): return true
    def render(self, req):
        self.d = Deferred(self.gen(req))
        self.d.addErrback(lambda fail: fail.printTraceback())
        self.d.addBoth(lambda ret: req.finish() or ret)
        return server.NOT_DONE_YET
