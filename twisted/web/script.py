"""I contain PythonScript, which is a very simple python script resource.
"""

import server
import resource
import html


from twisted import copyright
import cStringIO
StringIO = cStringIO
del cStringIO
import traceback

class PythonScript(resource.Resource):
    """I am an extremely simple dynamic resource; an embedded python script.

    This will execute a file (usually of the extension '.epy') as Python code,
    internal to the webserver.
    """
    isLeaf = 1
    def __init__(self, filename):
        """Initialize me with a script name.
        """
        self.filename = filename

    def render(self, request):
        """Render me to a web client.

        Load my file, execute it in a special namespace (with 'request' and
        '__file__' global vars) and finish the request.  Output to the web-page
        will NOT be handled with print - standard output goes to the log - but
        with request.write.
        """
        request.setHeader("x-powered-by","Twisted/%s" % copyright.version)
        namespace = {'request': request,
                     '__file__': self.filename}
        try:
            execfile(self.filename, namespace, namespace)
        except:
            io = StringIO.StringIO()
            traceback.print_exc(file=io)
            request.write(html.PRE(io.getvalue()))
        request.finish()
        return server.NOT_DONE_YET
    
