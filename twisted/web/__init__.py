# -*- test-case-name: twisted.web.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted Web: a L{web server<twisted.web.server>} (including an
L{HTTP implementation<twisted.web.http>} and a
L{resource model<twisted.web.resource>}) and
a L{web client<twisted.web.client>}.
"""

from twisted.web._version import version
from twisted.python.versions import Version
from twisted.python.deprecate import deprecatedModuleAttribute

__version__ = version.short()

deprecatedModuleAttribute(
    Version('Twisted', 11, 1, 0),
    "Google module is deprecated. Use Google's API instead",
    __name__, "google")
