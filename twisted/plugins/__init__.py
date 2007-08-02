# -*- test-case-name: twisted.test.test_plugin -*-
# Copyright (c) 2005 Divmod, Inc.
# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Plugins go in directories on your PYTHONPATH named twisted/plugins:
this is the only place where an __init__.py is necessary, thanks to
the __path__ variable.

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
@author: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

from twisted.plugin import pluginPackagePaths
__path__.extend(pluginPackagePaths(__name__))
__all__ = []                    # nothing to see here, move along, move along
