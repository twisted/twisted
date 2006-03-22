from twisted.web2 import http, resource

class HelloWorld(resource.Resource):
    def render(self, req):
        return http.Response(200, stream="Hello, World!")
