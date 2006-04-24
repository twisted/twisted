# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 
'''
The Twisted Documentation Generation System

Maintainer: U{Andrew Bennetts<mailto:spiv@twistedmatrix.com>}
'''

# TODO
# Abstract
# Bibliography
# Index
# Allow non-web image formats (EPS, specifically)
# Allow pickle output and input to minimize parses
# Numbered headers
# Navigational aides

from twisted.python import versions

version = versions.Version(__name__, 0, 1, 0)
__version__ = version.short()

del versions
