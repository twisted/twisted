
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

"""I am a simple test resource.
"""

from twisted.python import log
from twisted.web import static

class Test(static.Data):
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

