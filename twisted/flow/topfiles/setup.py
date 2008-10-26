# Copyright (c) 2008 Twisted Matrix Laboratories.
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
        twisted_subproject="flow",
        # metadata
        name="Twisted Flow",
        description="A Twisted concurrency programming library.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Clark Evans",
        url="http://twistedmatrix.com/trac/wiki/TwistedFlow",
        license="MIT",
        long_description="""\
Twisted Flow aims to make asynchronous programming a easier,
using python generators.
""",
        )
