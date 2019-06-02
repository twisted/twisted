# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted's unit tests.
"""


from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version
import proto_helpers

for i in proto_helpers.__all__:
    deprecatedModuleAttribute(
        Version('Twisted', 'NEXT', 0, 0),
        'Please use twisted.internet.testing.{} instead.'.format(i),
        __name__,
        i)

