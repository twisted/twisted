# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to get host information from a request object.

To test the script, rename the file to report.rpy, and move it to any directory,
let's say /var/www/html/.

Now, start your Twist web server:
   $ twistd -n web --path /var/www/html/

Then visit http://127.0.0.1:8080/report.rpy in your web browser.
"""

from twisted.web.resource import Resource


class ReportResource(Resource):

    def render_GET(self, request):
        path = request.path
        host = request.getHost().host
        port = request.getHost().port
        url = request.prePathURL()
        uri = request.uri
        secure = (request.isSecure() and "securely") or "insecurely"
        return ("""\
<HTML>
    <HEAD><TITLE>Welcome To Twisted Python Reporting</title></head>

    <BODY><H1>Welcome To Twisted Python Reporting</H1>
    <UL>
    <LI>The path to me is %(path)s
    <LI>The host I'm on is %(host)s
    <LI>The port I'm on is %(port)s
    <LI>I was accessed %(secure)s
    <LI>A URL to me is %(url)s
    <LI>My URI to me is %(uri)s
    </UL>
    </body>
</html>""" % vars())

resource = ReportResource()
