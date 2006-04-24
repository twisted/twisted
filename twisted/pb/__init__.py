"""Perspective Broker"""

from twisted.python import versions

version = versions.Version(__name__, 0, 0, 0)
__version__ = version.short()

del versions

