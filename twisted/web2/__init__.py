
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""

Twisted Web: a Twisted Web Server.

"""
import compat
from twisted.python import components
components.registerAdapter(compat.OldRequestAdapter, iweb.IRequest, iweb.IOldRequest)
