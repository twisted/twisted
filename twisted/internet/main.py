# -*- test-case-name: twisted.test.test_app -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Backwards compatability, and utility functions.

In general, this module should not be used, other than by reactor authors
who need to use the 'installReactor' method.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

import error

CONNECTION_DONE = error.ConnectionDone('Connection done')
CONNECTION_LOST = error.ConnectionLost('Connection lost')

def installReactor(reactor):
    # this stuff should be common to all reactors.
    import twisted.internet
    import sys
    assert not sys.modules.has_key('twisted.internet.reactor'), \
           "reactor already installed"
    twisted.internet.reactor = reactor
    sys.modules['twisted.internet.reactor'] = reactor

__all__ = ["CONNECTION_LOST", "CONNECTION_DONE", "installReactor"]
