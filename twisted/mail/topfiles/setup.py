import os, sys

import distutils

from twisted import copyright
from twisted.python import dist, util

# 2.2 doesn't have __file__ in main-scripts.
try:
    __file__
except NameError:
    __file__ = sys.argv[0]

def dict(**kw): return kw

dotdot = os.path.normpath(util.sibpath(__file__, '..'))
ver = copyright.version.replace('-', '_') #RPM doesn't like '-'

setup_args = dict(
    # metadata
    name="Twisted Mail",
    version=ver,
    description="Twisted Mail is a mail server.",
    author="Twisted Matrix Laboratories",
    author_email="twisted-python@twistedmatrix.com",
    maintainer="Jp Calderone",
    maintainer_email="exarkun@divmod.com",
    url="http://twistedmatrix.com/projects/mail/",
    license="MIT",
    long_description="Twisted Mail is a mail server.",

    # build stuff
    packages=dist.getPackages(dotdot, parent="twisted"),
    data_files=dist.getDataFiles(dotdot),
)

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

if __name__ == '__main__':
    dist.setup(**setup_args)

