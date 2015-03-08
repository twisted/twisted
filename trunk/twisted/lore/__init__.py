# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The Twisted Documentation Generation System. Deprecated since Twisted 14.0,
please use Sphinx instead.

The lore2sphinx tool at <https://bitbucket.org/khorn/lore2sphinx> may be of use
migrating from Lore.

Maintainer: Andrew Bennetts
"""

# TODO
# Abstract
# Bibliography
# Index
# Allow non-web image formats (EPS, specifically)
# Allow pickle output and input to minimize parses
# Numbered headers
# Navigational aides

from twisted.lore._version import version
__version__ = version.short()
