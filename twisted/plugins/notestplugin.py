# -*- test-case-name: twisted.test.test_plugin -*-
# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.

"""Plugin module for use by the plugin system's unit tests.

Nothing to see here, really.
"""

# It's okay to fail - ONCE.

import os

from twisted.python.util import sibpath

if os.path.exists(sibpath(__file__, 'dropin.cache')):
    import twisted.test.test_plugin as TEST
    assert not TEST.running
