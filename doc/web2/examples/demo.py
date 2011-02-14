#!/usr/bin/python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""I am a simple test resource.
"""
import os.path
import cgi as pycgi

from twisted.web2 import log
from twisted.web2 import static, wsgi, resource, responsecode, twcgi
from twisted.web2 import stream, http, http_headers
from twisted.internet import reactor

### A demo WSGI application.
def simple_wsgi_app(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/html; charset=ISO-8859-1')]
    start_response(status, response_headers)
    data = environ['wsgi.input'].read()
    environ['wsgi.errors'].write("This is an example wsgi error message\n")
    s = '<pre>'
    items=environ.items()
    items.sort()
    for k,v in items:
        s += repr(k)+': '+repr(v)+'\n'
    return [s, '<p><form method="POST" enctype="multipart/form-data"><input name="fo&quot;o" />\nData:<pre><input type="file" name="file"/><br/><input type="submit" /><br /></form>', data, '</pre>']


### Demonstrate a simple resource which renders slowly.
class Sleepy(resource.Resource):
    def render(self, req):
        # Create a stream object which can be written in pieces.
        s=stream.ProducerStream()
        # Write a string, and then, later, write another string, and
        # call it done.  (Also write spaces so browsers don't wait
        # before displaying anything at all)
        s.write("Hello\n")
        s.write(' '*10000+'\n')
        reactor.callLater(1, s.write, "World!\n")
        reactor.callLater(2, s.finish)
        # Return a response. Use the default response code of OK, and
        # the default headers
        return http.Response(stream=s)

### Form posting
class FormPost(resource.PostableResource):
    def render(self, req):
        return http.Response(responsecode.OK,
                             {'content-type': http_headers.MimeType('text', 'html')},
                             """
        Form1, x-www-form-urlencoded:
        <form method="POST" enctype="x-www-form-urlencoded">
        <input name="foo">
        <input name="bar" type="checkbox">
        <input type="submit">
        </form>
        <p>
        Form2, multipart/form-data:
        <form method="POST" enctype="multipart/form-data">
        <input name="foo">
        <input name="bar" type="file">
        <input type="submit">
        </form>
        <p>
        Arg dict: %r, Files: %r""" % (req.args, req.files))

### Toplevel resource. This is a more normal resource.
class Toplevel(resource.Resource):
    # addSlash=True to make sure it's treated as a directory-like resource
    addSlash=True

    # Render the resource. Here the stream is a string, which will get
    # adapted to a MemoryStream object.
    def render(self, req):
        contents = """<html>
<head><title>Twisted.web2 demo server</title><head>
<body>

Hello!  This is a twisted.web2 demo.
<ul>
<li><a href="file">Static File</a></li>
<li><a href="dir/">Static dir listing</a></li>
<li><a href="sleepy">Resource that takes time to render</a></li>
<li><a href="wsgi">WSGI app</a></li>
<li><a href="cgi">CGI app</a></li>
<li><a href="forms">Forms</a></li>
</ul>

</body>
</html>"""

        return http.Response(
            responsecode.OK,
            {'content-type': http_headers.MimeType('text', 'html')},
            contents)

    # Add some child resources
    child_file = static.File(os.path.join(os.path.dirname(resource.__file__), 'TODO'))
    child_dir = static.File('.')
    child_sleepy = Sleepy()
    child_wsgi = wsgi.WSGIResource(simple_wsgi_app)
    child_cgi = twcgi.FilteredScript(pycgi.__file__, filters=["/usr/bin/python"])
    child_forms = FormPost()

######## Demonstrate a bunch of different deployment options ########
### You likely only want one of these for your app.


# This part gets run when you run this file via: "twistd -noy demo.py"
if __name__ == '__builtin__':
    from twisted.application import service, strports
    from twisted.web2 import server, vhost, channel
    from twisted.python import util

    # Create the resource we will be serving
    test = Toplevel()

    # Setup default common access logging
    res = log.LogWrapperResource(test)
    log.DefaultCommonAccessLoggingObserver().start()

    # Create the site and application objects
    site = server.Site(res)
    application = service.Application("demo")

    # Serve it via standard HTTP on port 8080
    s = strports.service('tcp:8080', channel.HTTPFactory(site))
    s.setServiceParent(application)

    # Serve it via HTTPs on port 8081
    certPath = util.sibpath(__file__, os.path.join("..", "..", "core", "examples", "server.pem"))
    s = strports.service('ssl:8081:privateKey=%s' % certPath, channel.HTTPFactory(site))
    s.setServiceParent(application)

    # Serve it via SCGI on port 3000
    s = strports.service('tcp:3000', channel.SCGIFactory(site))
    s.setServiceParent(application)

    # Serve it via FastCGI on port 3001
    s = strports.service('tcp:3001', channel.FastCGIFactory(site))
    s.setServiceParent(application)

    # Serve it via HTTP on port 8538, with a url rewriter for running behind apache1.
    # (See deployment documentation for apache setup)
    s = strports.service(
        'tcp:8538:interface=127.0.0.1',
        channel.HTTPFactory(server.Site(
            vhost.VHostURIRewrite('http://localhost/app/', test))))
    s.setServiceParent(application)


# This bit gets run when you run this script as a CGI from another webserver.
if __name__ == '__main__':
    from twisted.web2 import channel, server
    toplevel = Toplevel()
    channel.startCGI(server.Site(toplevel))
