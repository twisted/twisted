
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I am a simple test resource.
"""

from twisted.python import log
from twisted.web import static

class Test(static.Data):
    isLeaf = True
    def __init__(self):
        static.Data.__init__(
            self,
            """
            <html>
            <head><title>Temporary Test</title><head>
            <body>
            
            Hello!  This is a temporary test until a more sophisticated form
            demo can be put back in using more up-to-date Twisted APIs.
            
            </body>
            </html>
            """,
            "text/html")

