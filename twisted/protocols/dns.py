weburl = "http://projects.twistedmatrix.com/names"

__doc__ = """
DNS protocol support.

This module is DEPRECATED. It has been split off into a third party
package. Please see %s.

This is just a place-holder that imports from the third-party names
package for backwards compatibility. To use it, you need to install
the third-party names package.
""" % weburl



try:
    from twisted.names.dns import *
except ImportError:
    raise ImportError("You need to have the twisted.names package installed to use DNS. See %s." % (weburl,))

# I'll put this *after* the imports, because if there's an error,
# they'll see a similar message anyway. And this way, tests can try to
# import the module and skip if it's not found, with no warning.

import warnings
warnings.warn("twisted.protocols.dns is DEPRECATED. See %s." % (weburl,), DeprecationWarning)

