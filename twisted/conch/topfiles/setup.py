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

def dict(**kw): return kw

ver = copyright.version.replace('-', '_') #RPM doesn't like '-'
setup_args = dict(
    # metadata
    name="Twisted Conch",
    version=ver,
    description="Twisted Conch is a ssh implementation.",
    author="Twisted Matrix Laboratories",
    author_email="twisted-python@twistedmatrix.com",
    maintainer="Paul Swartz",
    maintainer_email="z3p@twistedmatrix.com",
    url="http://twistedmatrix.com/projects/conch/",
    license="MIT",
    long_description="Twisted conch is a ssh implementation.",

    # build stuff
    packages=['twisted.' + x for x in dist.getPackages(os.path.normpath(util.sibpath(__file__, '..')))],
    data_files=dist.getDataFiles(os.path.normpath(util.sibpath(__file__, '..'))),
)
print os.path.normpath(util.sibpath(__file__, '..'))
print setup_args['packages']

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

if __name__ == '__main__':
    dist.setup(**setup_args)

