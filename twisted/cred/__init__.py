
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Twisted Cred

Support for verifying credentials, and providing services to users based on
those credentials.

(This package was previously known as the module twisted.internet.passport.)
"""

from twisted.python.versions import Version
from twisted.python.deprecate import deprecatedModuleAttribute
deprecatedModuleAttribute(
        Version("Twisted", 14, 1, 0),
                "The PAM interaction is insecure "
                "and the upstream module is unmaintained.",
                "twisted.cred", "pamauth")
