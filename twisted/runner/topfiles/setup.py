import sys

from distutils.core import Extension

from twisted.python import dist

def detectExtensions(builder):
    if builder._check_header("rpc/rpc.h"):
        return [Extension("twisted.runner.portmap",
                               ["twisted/runner/portmap.c"],
                               define_macros=builder.define_macros)]
    else:
        builder.announce("Sun-RPC portmap support is unavailable on this "
                      "system (but that's OK, you probably don't need it "
                      "anyway).")

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="runner",
        # metadata
        name="Twisted Runner",
        version="SVN-Trunk",
        description="Twisted Runner is an inetd replacement.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Andrew Bennetts",
        maintainer_email="spiv@twistedmatrix.com",
        url="http://twistedmatrix.com/projects/runner/",
        license="MIT",
        long_description="""\
Twisted Runner is an inetd replacement.
""",
        # build stuff
        detectExtensions=detectExtensions,
    )
