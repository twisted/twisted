from __future__ import generators
from twisted.internet import reactor
from twisted.web import server, resource
from twisted.flow import flow

def render(req):
    req.write("""
       <html>
         <head>
           <title>Delayed Webpage</title></head>
         <body>
           <h1>Delayed Webpage</h1>
    """)
    yield flow.Cooperate(5)
    req.write("""
           <p>Delayed content</p>
         </body>
        </html>
    """)

class FlowResource(resource.Resource):
    def __init__(self, gen):
        resource.Resource.__init__(self)
        self.gen = gen
    def isLeaf(self): return true
    def render(self, req):
        self.d = flow.Deferred(self.gen(req))
        self.d.addCallback(lambda _: req.finish())
        return server.NOT_DONE_YET

def run(gen):
    print "visit http://localhost:8081/ to view"
    root = FlowResource(gen)
    site = server.Site(root)
    reactor.listenTCP(8081,site)
    reactor.run()

if __name__=='__main__':
    run(render)
