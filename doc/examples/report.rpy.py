from twisted.web.resource import Resource


class ReportResource(Resource):

    def render_GET(self, request):
        path = request.path
        _, host, port = request.getHost()
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
