# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""I am a simple test resource.
"""

from twisted.python import log
from twisted.web2 import static

class Test(static.Data):
    def __init__(self):
        static.Data.__init__(
            self,
"""<html>
<head><title>Temporary Test</title><head>
<body>

Hello!  This is a temporary test until a more sophisticated form
demo can be put back in using more up-to-date Twisted APIs.

</body>
</html>""",
            "text/html")

    def locateChild(self, ctx, segments):
        name = segments[0]
        if name == '':
            return self, ()
        if name == 'file':
            return static.File('/'), segments[1:]
        return None, ()

if __name__ == '__builtin__':
    # Running from twistd -y
    from twisted.application import service, strports
    from twisted.web2 import server
    res = Test()
    application = service.Application("demo")
    s = strports.service('8080', server.Site(res))
    s.setServiceParent(application)
