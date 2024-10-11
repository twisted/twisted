# -*- test-case-name: twisted.internet.test.test_main -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
This namespace is for backwards compatibility only.  See the new locations for
its previous contents.

@see: L{CONNECTION_DONE}
@see: L{CONNECTION_LOST}
@see: L{installReactor}
"""


from twisted.internet.error import CONNECTION_DONE, CONNECTION_LOST
from twisted.internet.reactors import installGlobalReactor as installReactor

# not in __all__ any more because we don't want to signal to pydoctor that we
# moved them, but referenced for pyflakes
CONNECTION_DONE
CONNECTION_LOST
installReactor
