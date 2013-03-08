"""
Twisted runer: run and monitor processes

Maintainer: Andrew Bennetts

classic inetd(8) support:
Future Plans: The basic design should be final.  There are some bugs that need
fixing regarding UDP and Sun-RPC support.  Perhaps some day xinetd
compatibility will be added.

procmon:monitor and restart processes
"""

from twisted.runner._version import version
__version__ = version.short()
