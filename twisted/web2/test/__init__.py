# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""

twisted.web.test: unittests for the Twisted Web, Web Server Framework

"""

# Heh heh. Too Evil to pass up. ;)
import __builtin__
__builtin__._http_headers_isBeingTested=True
import sys
import twisted.web2
if sys.modules.has_key('twisted.web2.http_headers'):
    reload(twisted.web2.http_headers)
else:
    from twisted.web2 import http_headers
del __builtin__._http_headers_isBeingTested
