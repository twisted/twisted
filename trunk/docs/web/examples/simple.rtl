# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demostrates how to render a page using a third-party template
system.

Usage:
    $ twistd -n web --process=.rtl=twisted.web.script.ResourceTemplate --path /path/to/examples/

And make sure Quixote is installed.
"""

from twisted.web.resource import Resource


class ExampleResource(Resource):

    def render_GET(self, request):
        """\
<HTML>
    <HEAD><TITLE> Welcome To Twisted Python </title></head>

    <BODY><ul>"""
        for i in range(10):
            '<LI>';i
        """</ul></body>
</html>"""


resource = ExampleResource()

