from twisted.web.resource import Resource


class ExampleResource(Resource):

    def render(self, request):
        return """\
<HTML>
    <HEAD><TITLE> Welcome To Twisted Python </title></head>

    <BODY>
    This is a demonstration of embedded python in a webserver.
    </body>
</html>"""


resource = ExampleResource()

