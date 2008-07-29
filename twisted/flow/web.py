# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Author: Clark Evans

""" flow.web

    This contains wrappers to apply flow to components in twisted.web.*

"""
from controller import Deferred
from twisted.web import resource, server
from twisted.python.failure import Failure

class Resource(resource.Resource):
    """
    A resource which uses flow in its page generation.

    Use it like this::

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

    def isLeaf(self):
        return true

    def render(self, req):
        self.d = Deferred(self.gen(req))
        self.d.addErrback(lambda fail: fail.printTraceback())
        self.d.addBoth(lambda ret: req.finish() or ret)
        return server.NOT_DONE_YET
