# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
See twisted.internet.interfaces.IReactor*.
"""
import sys
del sys.modules['twisted.internet.reactor']
from twisted.python import runtime
if runtime.platform.getType() == 'java':
    from twisted.internet import javareactor
    javareactor.install()
else:
    #from twisted.python import log
    #log.msg("Installing SelectReactor, since unspecified.")
    from twisted.internet import default
    default.install()
