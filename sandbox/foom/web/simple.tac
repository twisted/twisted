from twisted.application import service
from twisted.application import internet
import http

class Request(http.Request):
	def process(self):
		self.write("Headers:\n")
		self.write(str(self.in_headers))
		
	def handleContentChunk(self, data):
		print "handleContentChunk %s" % data
		self.write(data)
		
	def handleContentComplete(self):
		print "handleContentComplete"
		self.finish()
		
class HTTPFactory(http.HTTPFactory):
	requestFactory = Request

application = service.Application("simple")
internet.TCPServer(
    8080, 
    HTTPFactory(logPath="http.log")
).setServiceParent(application)
