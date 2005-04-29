# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""I am a simple test resource.
"""
import os.path
import cgi as pycgi

from twisted.web2 import log
from twisted.web2 import static, wsgi, resource, responsecode, twcgi
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
    # open("upload.txt", 'w').write(data)
    s = '<pre>'
    items=environ.items()
    items.sort()
    for k,v in items:
        s += repr(k)+': '+repr(v)+'\n'
    import time; time.sleep(5)
    return [s, '<p><form method="POST" enctype="multipart/form-data"><input name="fo&quot;o" />\nData:<pre><input type="file" name="file"/><br/><input type="submit" /><br /></form>', data, '</pre>']


class Foo(resource.Resource):
    addSlash=True
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
            """<html>
<head><title>Temporary Test</title><head>
<body>

Hello!  This is a twisted.web2 demo.
<ul>
<li><a href="file">Static File</a></li>
<li><a href="dir/">Static dir listing (needs nevow atm)</a></li>
<li><a href="foo">Resource that takes time to render</a></li>
<li><a href="wsgi">WSGI app</a></li>
<li><a href="cgi">CGI app</a></li>
</ul>

</body>
</html>""")
          

    child_file = static.File(os.path.join(os.path.dirname(resource.__file__), 'TODO'))
    child_dir = static.File('.')
    child_foo = Foo()
    child_wsgi = wsgi.WSGIResource(simple_app)
    child_cgi = twcgi.FilteredScript(pycgi.__file__, filters=["/usr/bin/python"])
    
if __name__ == '__builtin__':
    # Running from twistd -y
    from twisted.application import service, strports
    from twisted.web2 import server
    from twisted.internet.ssl import DefaultOpenSSLContextFactory
    from twisted.python import util

    res = Test()
    res = log.LogWrapperResource(res)
    site = server.Site(res)
    log.DefaultCommonAccessLoggingObserver().start()
    
    application = service.Application("demo")
    s = strports.service('tcp:8080:backlog=50', site)
    s.setServiceParent(application)
    s = strports.service('ssl:8081:backlog=50:privateKey=doc/core/examples/server.pem', site)
    s.setServiceParent(application)
