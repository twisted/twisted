

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.



"""Deprecated, use L{twisted.web.domhelpers} instead."""

from twisted.web.domhelpers import *

import warnings
warnings.warn("Use twisted.web.domhelpers - twisted.python.domhelpers is "
              "deprecated.", DeprecationWarning, stacklevel=2)
