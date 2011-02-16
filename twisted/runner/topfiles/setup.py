# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

try:
    from twisted.python.dist import setup, ConditionalExtension as Extension
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

extensions = [
    Extension("twisted.runner.portmap",
              ["twisted/runner/portmap.c"],
              condition=lambda builder: builder._check_header("rpc/rpc.h")),
]

if __name__ == '__main__':
    setup(
        twisted_subproject="runner",
        # metadata
        name="Twisted Runner",
        description="Twisted Runner is a process management library and inetd "
                    "replacement.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Andrew Bennetts",
        url="http://twistedmatrix.com/trac/wiki/TwistedRunner",
        license="MIT",
        long_description="""\
Twisted Runner contains code useful for persistent process management
with Python and Twisted, and has an almost full replacement for inetd.
""",
        # build stuff
        conditionalExtensions=extensions,
    )
