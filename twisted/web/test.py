"""I am a test application for twisted.web.
"""

#t.w imports
import html

import cStringIO
StringIO = cStringIO
del cStringIO

class Test(html.Interface):
    """I am a trivial example of a 'web application'.
    """
    isLeaf = 1
    def __init__(self):
        """Initialize.
        """
        html.Interface.__init__(self)

    def printargs(self, request):
        """Return an HTML table of all arguments passed to a request.
        """
        io = StringIO.StringIO()
        io.write("<table>")
        for k, v in request.args.items():
            io.write("<tr><td>")
            io.write(k)
            io.write("</td><td>")
            io.write(html.PRE(v[0]))
            io.write("</td></tr>")
        io.write("</table>")
        return io.getvalue()

    def crash(self):
        """Demo method that raises the exception '"kaboom"'
        """
        raise "kaboom"

    def other(self):
        """Returns a string.
        """
        return "Hello world!  This is an additional box with static text..."

    def content(self, request):
        """Some dummy content.

        The source code is a good example of the 'form' method of resource.
        """
        return self.box(request,
                        "It worked! (kinda)",
"""
You now have the twisted.web webserver installed!  This doesn't do
very much yet, but in the near future it will do all kinds of groovy things.
""" +
    self.runBox(request, "Form Test", self.form, request,
                [['text', 'Test Text', 'TestText', 'I am the eggman'],
                 ['string', 'Test String', 'TestString', 'They Are The Eggmen'],
                 ['menu', 'Menu Test', 'TestMenu', ['I', 'AM',
                                                    'THE', 'WALRUS']],
                 ['password', 'Goo Goo Ga Joob', 'TestPw', None],
                 ['file', 'Bloopy', 'TestFile', None]
                 ]) +
    self.runBox(request, "Arguments",
                 self.printargs, request) +
    self.runBox(request, "Sample Traceback",
                 self.crash) +
    self.runBox(request, "HI YING!",
                 self.other)
    )
