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
from distutils.core import Extension

from twisted import copyright
from twisted.python import dist, util

# 2.2 doesn't have __file__ in main-scripts.
try:
    __file__
except NameError:
    __file__ = sys.argv[0]

def detectExtensions(builder):
    """
    Determine which extension modules we should build on this system.
    """
    print ("Checking if C extensions can be compiled, don't be alarmed if "
           "a few compile errors are printed.")

    if not builder._compile_helper("#define X 1\n"):
        print "Compiler not found, skipping C extensions."
        return []

    # Extension modules to build.
    exts = [
        Extension("twisted.spread.cBanana",
                  ["twisted/spread/cBanana.c"],
                  define_macros=builder.define_macros),
        ]

    # urllib.unquote accelerator
    exts.append( Extension("twisted.protocols._c_urlarg",
                            ["twisted/protocols/_c_urlarg.c"],
                            define_macros=builder.define_macros) )

    if sys.platform == 'darwin':
        exts.append(
            Extension("twisted.internet.cfsupport",
                      ["twisted/internet/cfsupport/cfsupport.c"],
                      extra_compile_args=['-w'],
                      extra_link_args=['-framework','CoreFoundation',
                                       '-framework','CoreServices',
                                       '-framework','Carbon'],
                      define_macros=builder.define_macros))

    if sys.platform == 'win32':
        exts.append( Extension("twisted.internet.iocpreactor._iocp",
                                ["twisted/internet/iocpreactor/_iocp.c"],
                                libraries=["ws2_32", "mswsock"],
                                define_macros=builder.define_macros))

    return exts



## setup args ##

def dict(**kw): return kw

twisted_subprojects = ["conch", "flow", "lore", "mail", "names",
                       "news", "pair", "runner", "web", "web2",
                       "words", "xish"]

ver = copyright.version.replace('-', '_') #RPM doesn't like '-'
setup_args = dict(
    # metadata
    name="Twisted",
    version=ver,
    description="Twisted %s is a framework to build frameworks" % ver,
    author="Twisted Matrix Laboratories",
    author_email="twisted-python@twistedmatrix.com",
    maintainer="Glyph Lefkowitz",
    maintainer_email="glyph@twistedmatrix.com",
    url="http://twistedmatrix.com/",
    license="MIT",
    long_description="""\
Twisted is a framework to build frameworks. It is expected that one
day the project will expanded to the point that the framework will
seamlessly integrate with mail, web, DNS, netnews, IRC, RDBMSs,
desktop environments, and your toaster.
""",

    # build stuff
    packages=dist.getPackages(util.sibpath(__file__, 'twisted'),
                              ignore=twisted_subprojects),
    data_files=dist.getDataFiles(util.sibpath(__file__, 'twisted'),
                                 ignore=twisted_subprojects),
    detectExtensions=detectExtensions,
    scripts= [
        'bin/manhole', 'bin/mktap', 'bin/twistd',
        'bin/tap2deb', 'bin/tap2rpm', 'bin/tapconvert',
        'bin/tkmktap', 'bin/trial',
    ],
)
print setup_args['packages']
print setup_args['data_files']

if hasattr(distutils.dist.DistributionMetadata, 'get_keywords'):
    setup_args['keywords'] = "internet www tcp framework games"

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

# Include the post install script when building windows packages
# because it's executed after install-time
if os.name=='nt':
    setup_args['scripts'].append('win32/twisted_postinstall.py')

if __name__ == '__main__':
    dist.setup(**setup_args)

