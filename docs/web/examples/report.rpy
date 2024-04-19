# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to get host information from a request object.

To test the script, copy report.rpy to any directory,
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
        output = """
<HTML>
    <HEAD><TITLE>Welcome To Twisted Python Reporting</title></head>

    <BODY><H1>Welcome To Twisted Python Reporting</H1>
    <UL>
    <LI>The path to me is {path}
    <LI>The host I'm on is {host}
    <LI>The port I'm on is {port}
    <LI>I was accessed {secure}
    <LI>A URL to me is {url}
    <LI>My URI to me is {uri}
    </UL>
    </body>
</html>""".format(
            path=path, host=host, port=port, secure=secure, url=url, uri=uri
        )

        return output.encode("utf8")


resource = ReportResource()
