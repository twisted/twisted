
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


# dominput

from twisted.python import log
log.write("DeprecationWarning: twisted.web.dominput has been renamed twisted.web.woven.input.\n")
from twisted.web.woven.input import *
