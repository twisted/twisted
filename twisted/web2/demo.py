# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""I am a simple test resource.
"""
import os.path

from twisted.python import log
from twisted.web2 import static, wsgi, resource, responsecode
from twisted.web2 import resource, stream, http, http_headers
from twisted.internet import reactor

def simple_app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-type','text/html; charset=ISO-8859-1')]
    start_response(status, response_headers)
    data = environ['wsgi.input'].read()
    environ['wsgi.errors'].write("This is an error message\n")
    # return environ['wsgi.file_wrapper'](open('/etc/hostconfig'))
    open("upload.txt", 'w').write(data)
    return ['<form method="POST" enctype="multipart/form-data"><input name="fo&quot;o" />\nData:<pre><input type="file" name="file"/><br/><input type="submit" /><br /></form>', data, '</pre>']


class Foo(resource.Resource):
    def render(self, ctx):
        s=stream.ProducerStream()
        s.write("Hello")
        reactor.callLater(2, s.finish)
        return http.Response(200, stream=s)

class Test(resource.Resource):
    addSlash=True
    def render(self, ctx):
        return http.Response(
            responsecode.OK,
            {'content-type': http_headers.MimeType('text', 'html')},
            stream.MemoryStream("""<html>
<head><title>Temporary Test</title><head>
<body>

Hello!  This is a twisted.web2 demo.
<ul>
<li><a href="file">Static File</a></li>
<li><a href="dir/">Static dir listing (needs nevow atm)</a></li>
<li><a href="foo">Resource that takes time to render</a></li>
<li><a href="wsgi">WSGI app</a></li>
</ul>

</body>
</html>"""))
          

    child_file = static.File(os.path.join(os.path.dirname(resource.__file__), 'TODO'))
    child_dir = static.File('.')
    child_foo = Foo()
    child_wsgi = wsgi.WSGIResource(simple_app)

    
    
if __name__ == '__builtin__':
    # Running from twistd -y
    from twisted.application import service, strports
    from twisted.web2 import server
    res = Test()
    application = service.Application("demo")
    s = strports.service('tcp:8080:backlog=50', server.Site(res))
    s.setServiceParent(application)
