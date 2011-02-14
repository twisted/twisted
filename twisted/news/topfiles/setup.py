# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

try:
    from twisted.python import dist
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="news",
        # metadata
        name="Twisted News",
        description="Twisted News is an NNTP server and programming library.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        url="http://twistedmatrix.com/trac/wiki/TwistedNews",
        license="MIT",
        long_description="""\
Twisted News is an NNTP protocol (Usenet) programming library. The
library contains server and client protocol implementations. A simple
NNTP server is also provided.
""",
    )

