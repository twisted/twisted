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

$Id: setup.py,v 1.120 2003/07/04 14:03:55 exarkun Exp $
"""

import distutils, os, sys, string
from glob import glob

from distutils.core import setup, Extension
from distutils.command.install_scripts import install_scripts
from distutils.command.install_data import install_data
from distutils.ccompiler import new_compiler
from distutils.errors import CompileError
from distutils.command.build_ext import build_ext
from distutils import sysconfig

if sys.version_info<(2,2):
    print >>sys.stderr, "You must use at least Python 2.2 for Twisted"
    sys.exit(3)

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
                if not file.endswith(".py"):
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
                                        "twisted/internet/cReactor/cDelayedCall.c",
                                        "twisted/internet/cReactor/cSystemEvent.c",
                                    ],
                                    define_macros=define_macros) )
        else:
            self.announce("The C reactor is unavailable on this system (this is fine, don't worry about it, everything will still work).")

        # The portmap module (for inetd)
        if self._check_header("rpc/rpc.h"):
            exts.append( Extension("twisted.runner.portmap",
                                    ["twisted/runner/portmap.c"],
                                    define_macros=define_macros) )
        else:
            self.announce("Sun-RPC portmap support is unavailable on this system (but that's OK, you probably don't need it anyway).")

        # urllib.unquote accelerator
        exts.append( Extension("twisted.protocols._c_urlarg",
                                ["twisted/protocols/_c_urlarg.c"],
                                define_macros=define_macros) )

        # opendir/readdir/scandir wrapper
        if self._check_header("dirent.h"):
            exts.append( Extension("twisted.python.dir",
                                    ["twisted/python/dir.c"],
                                    define_macros=define_macros) )
        else:
            self.announce("scandir() wrapper is unavailable on this system (don't worry, everything will still work)")

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
    'license': "GNU LGPL",
    'long_description': """\
Twisted is a framework to build frameworks. It is expected that one
day the project will expanded to the point that the framework will
seamlessly integrate with mail, web, DNS, netnews, IRC, RDBMSs,
desktop environments, and your toaster.
""",
    'packages': [
        "twisted",
        "twisted.coil",
        "twisted.coil.plugins",
        "twisted.conch",
        "twisted.conch.ssh",
        "twisted.conch.ui",
        "twisted.conch.insults",
        "twisted.cred",
        "twisted.enterprise",
        "twisted.flow",
        "twisted.im",
        "twisted.internet",
        "twisted.internet.serialport",
        "twisted.lore",
        "twisted.mail",
        "twisted.manhole",
        "twisted.manhole.ui",
        "twisted.names",
        "twisted.news",
        "twisted.pair",
        "twisted.persisted",
        "twisted.persisted.journal",
        "twisted.popsicle",
        "twisted.protocols",
        "twisted.protocols.gps",
        "twisted.protocols.mice",
        "twisted.python",
        "twisted.runner",
        "twisted.scripts",
        "twisted.sibling",
        "twisted.spread",
        "twisted.spread.ui",
        "twisted.tap",
        "twisted.test",
        "twisted.trial",
        "twisted.web",
        "twisted.web.woven",
        "twisted.words",
        "twisted.world",
        "twisted.zoot",
    ],
    'scripts' : [
        'bin/manhole', 'bin/mktap', 'bin/twistd',
        'bin/im', 'bin/t-im', 'bin/tap2deb',
        'bin/tapconvert', 'bin/websetroot',
        'bin/lore',
        'bin/tkmktap', 'bin/conch', 'bin/ckeygen', 'bin/tktwistd',
        'bin/tkconch', 'bin/trial'
    ],
    'cmdclass': {
        'install_scripts': install_scripts_twisted,
        'install_data': install_data_twisted,
        'build_ext' : build_ext_twisted,
    },
}

# Apple distributes a nasty version of Python 2.2 w/ all release builds of
# OS X 10.2 and OS X Server 10.2
BROKEN_CONFIG = '2.2 (#1, 07/14/02, 23:25:09) \n[GCC Apple cpp-precomp 6.14]'
if sys.platform == 'darwin' and sys.version == BROKEN_CONFIG:
    # change this to 1 if you have some need to compile
    # with -flat_namespace as opposed to -bundle_loader
    FLAT_NAMESPACE = 0
    BROKEN_ARCH = '-arch i386'
    BROKEN_NAMESPACE = '-flat_namespace -undefined_suppress'
    import distutils.sysconfig
    distutils.sysconfig.get_config_vars()
    x = distutils.sysconfig._config_vars['LDSHARED']
    y = x.replace(BROKEN_ARCH, '')
    if not FLAT_NAMESPACE:
        e = os.path.realpath(sys.executable)
        y = y.replace(BROKEN_NAMESPACE, '-bundle_loader ' + e)
    if y != x:
        print "Fixing some of Apple's compiler flag mistakes..."
        distutils.sysconfig._config_vars['LDSHARED'] = y

if os.name=='nt':
    setup_args['scripts'].append('win32/twisted_postinstall.py')

if hasattr(distutils.dist.DistributionMetadata, 'get_keywords'):
    setup_args['keywords'] = "internet www tcp framework games"

if hasattr(distutils.dist.DistributionMetadata, 'get_platforms'):
    setup_args['platforms'] = "win32 posix"

imPath = os.path.join('twisted', 'im')
pbuiPath = os.path.join('twisted','spread','ui')
manuiPath = os.path.join('twisted','manhole','ui')
lorePath = os.path.join("twisted", 'lore')

testPath = os.path.join("twisted", 'test')
testFiles = ['server.pem', 'rfc822.message']

wovenPath = os.path.join('twisted', 'web', 'woven')
wovenFiles = ['FlashConduitGlue.html', 'WebConduitGlue.html',
              'FlashConduit.fla', 'WebConduit2_mozilla.js',
              'FlashConduit.swf', 'WebConduit2_msie.js']

setup_args['data_files']=[
    (imPath, [os.path.join(imPath, 'instancemessenger.glade')]),
    (pbuiPath, [os.path.join(pbuiPath, 'login2.glade')]),
    (manuiPath, [os.path.join(manuiPath, 'gtk2manhole.glade')]),
    (lorePath, [os.path.join(lorePath, "template.mgp")]),
    ('twisted', [os.path.join('twisted', 'plugins.tml')]),
    ]

for pathname, filenames in [(wovenPath, wovenFiles),
                            (testPath, testFiles)]:
    setup_args['data_files'].extend(
        [(pathname, [os.path.join(pathname, filename)])
            for filename in filenames])

win32doc='doc/win32doc.zip'
if os.path.exists(win32doc):
    setup_args['data_files'].append(('TwistedDocs', [win32doc]))

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
    setup(**setup_args)
