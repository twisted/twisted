# -*- test-case-name: twisted.test.test_plugin -*-
# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.

"""
Plugins go in directories on your PYTHONPATH named twisted/plugins:
this is the only place where an __init__.py is necessary, thanks to
the __path__ variable.

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
@author: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

import os, sys
__path__ = [os.path.abspath(os.path.join(x, 'twisted', 'plugins')) for x in sys.path]

__all__ = []                    # nothing to see here, move along, move along
