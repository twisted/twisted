import os, sys

import distutils
from distutils.core import setup, Extension

from twisted import copyright
from twisted.python import dist, util

# 2.2 doesn't have __file__ in main-scripts.
try:
    __file__
except NameError:
    __file__ = sys.argv[0]

class build_ext_twisted(dist.build_ext_twisted):
    def detectModules(self):
        if self._check_header("rpc/rpc.h"):
            return [Extension("twisted.runner.portmap",
                                   ["twisted/runner/portmap.c"],
                                   define_macros=self.define_macros)]
        else:
            self.announce("Sun-RPC portmap support is unavailable on this "
                          "system (but that's OK, you probably don't need it "
                          "anyway).")


def dict(**kw): return kw

ver = copyright.version.replace('-', '_') #RPM doesn't like '-'
setup_args = dict(
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
    packages=['twisted.runner'],#dist.getPackages(os.path.normpath(util.sibpath(__file__, '..'))),
    data_files=dist.getDataFiles(os.path.normpath(util.sibpath(__file__, '..'))),
    cmdclass={
        'build_scripts': dist.build_scripts_twisted,
        'install_data': dist.install_data_twisted,
        'build_ext' : build_ext_twisted,
    },
    ext_modules=[True], # Fucking Arg I Hate Distutils
)

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

if __name__ == '__main__':
    setup(**setup_args)

