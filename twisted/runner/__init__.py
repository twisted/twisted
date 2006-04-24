"""Twisted runer: run and monitor processes

Stability: semi-stable

Maintainer: U{Andrew Bennetts<mailto:spiv@twistedmatrix.com>}

classic inetd(8) support:
Future Plans: The basic design should be final.  There are some bugs that need
fixing regarding UDP and Sun-RPC support.  Perhaps some day xinetd
compatibility will be added.

procmon:monitor and restart processes
"""

from twisted.python import versions

version = versions.Version(__name__, 0, 1, 0)
__version__ = version.short()

del versions
