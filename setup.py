#!/usr/bin/env python

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils installer for Twisted.
"""
import os, sys

if sys.version_info < (2,2):
    print >>sys.stderr, "You must use at least Python 2.2 for Twisted"
    sys.exit(3)

import distutils
from distutils.core import setup, Extension

from twisted import copyright
from twisted.python import dist, util


class build_ext_twisted(dist.build_ext_twisted):
    def _detect_modules(self):
        """
        Determine which extension modules we should build on this system.
        """
        # always define WIN32 under Windows
        if os.name == 'nt':
            define_macros = [("WIN32", 1)]
        else:
            define_macros = []

        print ("Checking if C extensions can be compiled, don't be alarmed if "
               "a few compile errors are printed.")
        
        if not self._compile_helper("#define X 1\n"):
            print "Compiler not found, skipping C extensions."
            self.extensions = []
            return
        
        # Extension modules to build.
        exts = [
            Extension("twisted.spread.cBanana",
                      ["twisted/spread/cBanana.c"],
                      define_macros=define_macros),
            ]

        # The portmap module (for inetd)
        if self._check_header("rpc/rpc.h"):
            exts.append( Extension("twisted.runner.portmap",
                                   ["twisted/runner/portmap.c"],
                                   define_macros=define_macros) )
        else:
            self.announce("Sun-RPC portmap support is unavailable on this "
                          "system (but that's OK, you probably don't need it "
                          "anyway).")

        # urllib.unquote accelerator
        exts.append( Extension("twisted.protocols._c_urlarg",
                                ["twisted/protocols/_c_urlarg.c"],
                                define_macros=define_macros) )

        if sys.platform == 'darwin':
            exts.append(
                Extension("twisted.internet.cfsupport",
                          ["twisted/internet/cfsupport/cfsupport.c"],
                          extra_compile_args=['-w'],
                          extra_link_args=['-framework','CoreFoundation',
                                           '-framework','CoreServices',
                                           '-framework','Carbon'],
                          define_macros=define_macros))

        if sys.platform == 'win32':
            exts.append( Extension("twisted.internet.iocpreactor._iocp",
                                    ["twisted/internet/iocpreactor/_iocp.c"],
                                    libraries=["ws2_32", "mswsock"],
                                    define_macros=define_macros))

        self.extensions = exts



## setup args ##

def dict(**kw): return kw

ver = copyright.version.replace('-', '_') #RPM doesn't like '-'
setup_args = dict(
    name="Twisted",
    version=ver,
    description="Twisted %s is a framework to build frameworks" % ver,
    author="Twisted Matrix Laboratories",
    author_email="twisted-python@twistedmatrix.com",
    maintainer="Glyph Lefkowitz",
    maintainer_email="glyph@twistedmatrix.com",
    url="http://twistedmatrix.com/",
    license="GNU LGPL",
    long_description="""\
Twisted is a framework to build frameworks. It is expected that one
day the project will expanded to the point that the framework will
seamlessly integrate with mail, web, DNS, netnews, IRC, RDBMSs,
desktop environments, and your toaster.
""",
    packages=dist.getPackages(util.sibpath(__file__, 'twisted')),
    data_files=dist.getDataFiles(util.sibpath(__file__, 'twisted')),
    scripts= [
        'bin/manhole', 'bin/mktap', 'bin/twistd',
        'bin/words/im', 'bin/t-im', 'bin/tap2deb', 'bin/tap2rpm',
        'bin/tapconvert', 'bin/web/websetroot',
        'bin/lore/lore',
        'bin/tkmktap', 'bin/conch/conch', 'bin/conch/ckeygen',
        'bin/conch/tkconch', 'bin/trial', 'bin/mail/mailmail'
    ],
    cmdclass={
        'build_scripts': dist.build_scripts_twisted,
        'install_data': dist.install_data_twisted,
        'build_ext' : build_ext_twisted,
    },
    ext_modules=[True], # Fucking Arg I Hate Distutils
)

if hasattr(distutils.dist.DistributionMetadata, 'get_keywords'):
    setup_args['keywords'] = "internet www tcp framework games"

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

# Include the post install script when building windows packages
# because it's executed after install-time
if os.name=='nt':
    setup_args['scripts'].append('win32/twisted_postinstall.py')

if __name__ == '__main__':
    setup(**setup_args)

