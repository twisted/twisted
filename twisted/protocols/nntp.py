weburl = "http://projects.twistedmatrix.com/news"

__doc__ = """
NNTP protocol support.

This module is DEPRECATED. It has been split off into a third party
package. Please see %s.

This is just a place-holder that imports from the third-party news
package for backwards compatibility. To use it, you need to install
the third-party news package.
""" % weburl



try:
    from twisted.news.nntp import *
except ImportError:
    raise ImportError("You need to have the twisted.news package installed to use NNTP. See %s." % (weburl,))

# I'll put this *after* the imports, because if there's an error,
# they'll see a similar message anyway. And this way, tests can try to
# import the module and skip if it's not found, with no warning.

import warnings
warnings.warn("twisted.protocols.nntp is DEPRECATED. See %s." % (weburl,), DeprecationWarning)

