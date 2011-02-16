# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

try:
    from twisted.python import dist
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="web2",
        # metadata
        name="Twisted Web2",
        description="Twisted Web2 is a web server.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="James Knight",
        url="http://twistedmatrix.com/trac/wiki/TwistedWeb2",
        license="MIT",
        long_description="Twisted Web2 is a web server.",
        )
