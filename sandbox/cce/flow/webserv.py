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
