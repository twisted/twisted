
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""

Twisted Web: a Twisted Web Server.

"""
version = "TwistedWeb/2.0a3"

import compat, http, iweb, stream
from twisted.python import components

components.registerAdapter(compat.OldRequestAdapter, iweb.IRequest, iweb.IOldRequest)
components.registerAdapter(compat.OldResourceAdapter, iweb.IOldResource, iweb.IResource)
components.registerAdapter(http.Response, int, iweb.IResponse)

del components
