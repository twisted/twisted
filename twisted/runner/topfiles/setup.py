import os, sys

import distutils
from distutils.core import Extension

from twisted import copyright
from twisted.python import dist, util

# 2.2 doesn't have __file__ in main-scripts.
try:
    __file__
except NameError:
    __file__ = sys.argv[0]

def detectExtensions(builder):
    if builder._check_header("rpc/rpc.h"):
        return [Extension("twisted.runner.portmap",
                               ["twisted/runner/portmap.c"],
                               define_macros=builder.define_macros)]
    else:
        builder.announce("Sun-RPC portmap support is unavailable on this "
                      "system (but that's OK, you probably don't need it "
                      "anyway).")


def dict(**kw): return kw

dotdot = os.path.normpath(util.sibpath(__file__, '..'))
twistedpath = os.path.normpath(os.path.join(dotdot, '..', '..'))

ver = copyright.version.replace('-', '_') #RPM doesn't like '-'

setup_args = dict(
    # metadata
    name="Twisted Runner",
    version=ver,
    description="Twisted Runner is an inetd replacement.",
    author="Twisted Matrix Laboratories",
    author_email="twisted-python@twistedmatrix.com",
    maintainer="Andrew Bennetts",
    maintainer_email="spiv@twistedmatrix.com",
    url="http://twistedmatrix.com/projects/runner/",
    license="MIT",
    long_description="Twisted Runner is an inetd replacement.",

    # build stuff
    packages=dist.getPackages(dotdot, parent="twisted"),
    data_files=dist.getDataFiles(dotdot, parent=twistedpath),
    detectExtensions=detectExtensions,
)
print setup_args['data_files']

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

if __name__ == '__main__':
    dist.setup(**setup_args)

