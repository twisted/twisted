#! /usr/bin/env python

# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Package installer for Twisted

Copyright (C) 2001 Matthew W. Lefkowitz
All rights reserved, see LICENSE for details.

$Id: setup.py,v 1.78 2002/12/05 07:59:26 moshez Exp $
"""

import distutils, os, sys, string
from glob import glob

from distutils.core import setup, Extension
from distutils.command.install_scripts import install_scripts
from distutils.command.install_data import install_data
from distutils.ccompiler import new_compiler
from distutils.errors import CompileError
from distutils.command.build_ext import build_ext

from twisted import copyright


#############################################################################
### Helpers and distutil tweaks
#############################################################################

class install_scripts_twisted(install_scripts):
    """Renames scripts so they end with '.py' on Windows."""

    def run(self):
        install_scripts.run(self)
        if os.name == "nt":
            for file in self.get_outputs():
                os.rename(file, file + ".py")


# make sure data files are installed in twisted package
# this is evil.
class install_data_twisted(install_data):
    def finalize_options (self):
        self.set_undefined_options('install',
            ('install_lib', 'install_dir')
        )
        install_data.finalize_options(self)


# Custom build_ext command simlar to the one in Python2.1/setup.py.  This
# allows us to detect (only at build time) what extentions we want to build.

class build_ext_twisted(build_ext):

    def build_extensions(self):
        """
        Override the build_ext build_extensions method to call our module detection
        function before it trys to build the extensions.
        """

        self._detect_modules()
        build_ext.build_extensions(self)


    def _check_header(self, header_name):
        """
        Check if the given header can be included by trying to compile a file
        that contains only an #include line.
        """
        compiler = new_compiler()
        compiler.announce("checking for %s ..." % header_name, 0)

        conftest = open("conftest.c", "w")
        conftest.write("#include <%s>\n" % header_name)
        conftest.close()

        # Attempt to compile the file, I wish I could use compiler.preprocess
        # instead but it defaults to None in unixccompiler.py.
        ok = 1
        try:
            compiler.compile(["conftest.c"], output_dir='')
        except CompileError:
            ok = 0

        # Cleanup
        try:
            os.unlink("conftest.c")
            os.unlink("conftest.o")
        except:
            pass

        return ok


    def _detect_modules(self):
        """
        Determine which extension modules we should build on this system.
        """

        # always define WIN32 under Windows
        if os.name == 'nt':
            define_macros = [("WIN32", 1)]
        else:
            define_macros = []
        
        # Extension modules to build.
        exts = [
            Extension("twisted.spread.cBanana",
                      ["twisted/spread/cBanana.c"],
                      define_macros=define_macros),
            ]

        # The C reactor
        # if python has poll support, no doubt OS supports
        try:
            import select
        except:
            select = None
        try:
            import thread
        except:
            thread = None
        if hasattr(select, "poll") and thread:
            exts.append( Extension("twisted.internet.cReactor",
                                    [
                                        "twisted/internet/cReactor/cReactorModule.c",
                                        "twisted/internet/cReactor/cReactor.c",
                                        "twisted/internet/cReactor/cReactorTime.c",
                                        "twisted/internet/cReactor/cReactorTCP.c",
                                        "twisted/internet/cReactor/cReactorTransport.c",
                                        "twisted/internet/cReactor/cReactorBuffer.c",
                                        "twisted/internet/cReactor/cReactorUtil.c",
                                        "twisted/internet/cReactor/cReactorThread.c",
                                    ],
                                    define_macros=define_macros) )
        else:
            self.announce("The C reactor is unavailable on this system (this is fine, don't worry about it, everything will still work).")

        # The portmap module (for inetd)
        if self._check_header("rpc/pmap_clnt.h"):
            exts.append( Extension("twisted.runner.portmap",
                                    ["twisted/runner/portmap.c"],
                                    define_macros=define_macros) )
        else:
            self.announce("Sun-RPC portmap support is unavailable on this system (but that's OK, you probably don't need it anyway).")

        self.extensions.extend(exts)


#############################################################################
### Call setup()
#############################################################################

ver = string.replace(copyright.version, '-', '_') #RPM doesn't like '-'
setup_args = {
    'name': "Twisted",
    'version': ver,
    'description': "Twisted %s is a framework to build frameworks" % ver,
    'author': "Twisted Matrix Laboratories",
    'author_email': "twisted-python@twistedmatrix.com",
    'maintainer': "Glyph Lefkowitz",
    'maintainer_email': "glyph@twistedmatrix.com",
    'url': "http://twistedmatrix.com/",
    'licence': "GNU LGPL",
    'long_description': """
Twisted is a framework to build frameworks. It is expected that one day
the project has expanded to the point that the Twisted Reality framework
(a very small part of the codebase, even now) can seamlessly integrate
with mail, web, DNS, netnews, IRC, RDBMSs, desktop environments, and
your toaster. 
""",
    'packages': [
        "twisted",
        "twisted.coil",
        "twisted.coil.plugins",
        "twisted.conch",
        "twisted.conch.ssh",
        "twisted.cred",
        "twisted.enterprise",
        "twisted.im",
        "twisted.inetd",
        "twisted.internet",
        "twisted.lore",
        "twisted.mail",
        "twisted.manhole",
        "twisted.manhole.ui",
        "twisted.names",
        "twisted.news",
        "twisted.persisted",
        "twisted.persisted.journal",
        "twisted.protocols",
        "twisted.protocols.mice",
        "twisted.python",
        "twisted.scripts",
        "twisted.sister",
        "twisted.spread",
        "twisted.spread.ui",
        "twisted.tap",
        "twisted.test",
        "twisted.web",
        "twisted.web.woven",
        "twisted.words",
        "twisted.zoot",
    ],
    'scripts' : [
        'bin/manhole', 'bin/mktap', 'bin/twistd',
        'bin/im', 'bin/t-im', 'bin/tap2deb',
        'bin/coil', 'bin/tapconvert', 'bin/websetroot',
        'bin/generatelore', 'bin/html2latex', 'bin/hlint',
        'bin/tkmktap', 'bin/conch',
    ],
    'cmdclass': {
        'install_scripts': install_scripts_twisted,
        'install_data': install_data_twisted,
        'build_ext' : build_ext_twisted,
    },
}

if hasattr(distutils.dist.DistributionMetadata, 'get_keywords'):
    setup_args['keywords'] = "internet www tcp framework games"

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

imPath = os.path.join('twisted', 'im')
setup_args['data_files'] = [(imPath, [os.path.join(imPath, 'instancemessenger.glade')]),
                            ('twisted', [os.path.join('twisted', 'plugins.tml')])]

# always define WIN32 under Windows
if os.name == 'nt':
    define_macros = [("WIN32", 1)]
else:
    define_macros = []

# Include all extension modules here, whether they are built or not.
# The custom built_ext command will wipe out this list anyway, but it
# is required for sdist to work.

#X-platform:
if not (sys.argv.count("bdist_wininst") and os.name != 'nt'):
    setup_args['ext_modules'] = [
        Extension("twisted.spread.cBanana",
                  ["twisted/spread/cBanana.c"],
                  define_macros=define_macros),
    ]
else:
    setup_args['ext_modules'] = []

if __name__ == '__main__':
    apply(setup, (), setup_args)
