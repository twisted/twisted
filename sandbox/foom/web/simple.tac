from twisted.application import service
from twisted.application import internet
from twisted.internet import reactor
import http

class Request(http.Request):
    def process(self):
        if self.uri[0] == '/':
            self.uri = self.uri[1:]
        delay = int(self.uri)
        if delay > 0:
            reactor.callLater(delay, self.doit)
        else:
            self.doit()

    def doit(self):
        self.acceptData()
        self.write("Headers:\n")
        self.write(str(self.in_headers))
        self.finish()
        
    def handleContentChunk(self, data):
        print "handleContentChunk %s" % data
#        self.write(data)
        
    def handleContentComplete(self):
        print "handleContentComplete"
        
class HTTPFactory(http.HTTPFactory):
    requestFactory = Request

application = service.Application("simple")
internet.TCPServer(
    8080, 
    HTTPFactory(logPath="http.log")
).setServiceParent(application)
