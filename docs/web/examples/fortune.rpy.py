# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This example demonstrates how to render the output of a system process to a
twisted web server.

In order to run this, you need to have fortune installed.  Fortune is a simple
game that displays a random message from a database of quotations. You will need
to change the path of the fortune program if it's not in the "/usr/game"
directory.

To test the script, rename the file to fortune.rpy, and move it to any
directory, let's say /var/www/html/

Now, start your Twisted web server:
    $ twistd -n web --path /var/www/html/

And visit http://127.0.0.1:8080/fortune.rpy with a web browser.
"""

from twisted.web.resource import Resource
from twisted.web import server
from twisted.internet import utils
from twisted.python import util

class FortuneResource(Resource):
    """
    This resource will only respond to HEAD & GET requests.
    """
    # Link your fortune program to /usr/games or change the path.
    fortune = "/usr/games/fortune"

    def render_GET(self, request):
        """
        Get a fortune and serve it as the response to this request.

        Use L{utils.getProcessOutput}, which spawns a process and returns a
        Deferred which fires with its output.
        """
        request.write("<pre>\n")
        deferred = utils.getProcessOutput(self.fortune)
        deferred.addCallback(lambda s:
                             (request.write(s+"\n"), request.finish()))
        deferred.addErrback(lambda s:
                     (request.write(str(s)), request.finish()))
        return server.NOT_DONE_YET

resource = FortuneResource()
