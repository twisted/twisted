
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""I contain PythonScript, which is a very simple python script resource.
"""

import server
import resource
import html
import error

from twisted.protocols import http
from twisted import copyright
import cStringIO
StringIO = cStringIO
del cStringIO
import traceback

def PyCompiler(path):
    """
    I am a normal py file which will define a "resource" global upon completion
    The resource global should be an instance of Resource, and will be returned
    """
    globals = {}

    execfile(path, globals, globals)
    
    return globals['resource']

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
        except IOError, e:
            if e.errno == 2: #file not found
                request.setResponseCode(http.NOT_FOUND)
                request.write(error.NoResource("File not found.").render(request))
        except:
            io = StringIO.StringIO()
            traceback.print_exc(file=io)
            request.write(html.PRE(io.getvalue()))
        request.finish()
        return server.NOT_DONE_YET
