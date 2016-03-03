# -*- test-case-name: twisted.python.test.test_dist -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils convenience functionality.

Don't use this outside of Twisted.

Maintainer: Christopher Armstrong

@var _EXTRA_OPTIONS: These are the actual package names and versions that will
    be used by C{extras_require}.  This is not passed to setup directly so that
    combinations of the packages can be created without the need to copy
    package names multiple times.

@var _EXTRAS_REQUIRE: C{extras_require} is a dictionary of items that can be
    passed to setup.py to install optional dependencies.  For example, to
    install the optional dev dependencies one would type::

        pip install -e ".[dev]"

    This has been supported by setuptools since 0.5a4.

@var _PLATFORM_INDEPENDENT: A list of all optional cross-platform dependencies,
    as setuptools version specifiers, used to populate L{_EXTRAS_REQUIRE}.
"""

from distutils.command import build_scripts, build_ext
from distutils.errors import CompileError
from setuptools import setup as _setup
from setuptools import Extension
import fnmatch
import os
import platform
import sys

from twisted import copyright
from twisted.python.compat import execfile

STATIC_PACKAGE_METADATA = dict(
    name="Twisted",
    version=copyright.version,
    description="An asynchronous networking framework written in Python",
    author="Twisted Matrix Laboratories",
    author_email="twisted-python@twistedmatrix.com",
    maintainer="Glyph Lefkowitz",
    maintainer_email="glyph@twistedmatrix.com",
    url="http://twistedmatrix.com/",
    license="MIT",
    long_description="""\
An extensible framework for Python programming, with special focus
on event-based network programming and multiprotocol integration.
""",
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        ],
    )



_EXTRA_OPTIONS = dict(
    dev=['twistedchecker >= 0.4.0',
         'pyflakes >= 1.0.0',
         'twisted-dev-tools >= 0.0.2',
         'python-subunit',
         'sphinx >= 1.3.1',
         'pydoctor >= 15.0.0'],
    tls=['pyopenssl >= 0.13',
         'service_identity',
         'idna >= 0.6'],
    conch=['gmpy',
           'pyasn1',
           'cryptography >= 0.9.1',
           ],
    soap=['soappy'],
    serial=['pyserial'],
    osx=['pyobjc'],
    windows=['pypiwin32']
)

_PLATFORM_INDEPENDENT = (
    _EXTRA_OPTIONS['tls'] +
    _EXTRA_OPTIONS['conch'] +
    _EXTRA_OPTIONS['soap'] +
    _EXTRA_OPTIONS['serial']
)

_EXTRAS_REQUIRE = {
    'dev': _EXTRA_OPTIONS['dev'],
    'tls': _EXTRA_OPTIONS['tls'],
    'conch': _EXTRA_OPTIONS['conch'],
    'soap': _EXTRA_OPTIONS['soap'],
    'serial': _EXTRA_OPTIONS['serial'],
    'all_non_platform': _PLATFORM_INDEPENDENT,
    'osx_platform': (
        _EXTRA_OPTIONS['osx'] + _PLATFORM_INDEPENDENT
    ),
    'windows_platform': (
        _EXTRA_OPTIONS['windows'] + _PLATFORM_INDEPENDENT
    ),
}


class ConditionalExtension(Extension):
    """
    An extension module that will only be compiled if certain conditions are
    met.

    @param condition: A callable of one argument which returns True or False to
        indicate whether the extension should be built. The argument is an
        instance of L{build_ext_twisted}, which has useful methods for checking
        things about the platform.
    """
    def __init__(self, *args, **kwargs):
        self.condition = kwargs.pop("condition", lambda builder: True)
        Extension.__init__(self, *args, **kwargs)



def setup(**kw):
    """
    An alternative to distutils' setup() which is specially designed
    for Twisted subprojects.

    @param conditionalExtensions: Extensions to optionally build.
    @type conditionalExtensions: C{list} of L{ConditionalExtension}
    """
    return _setup(**get_setup_args(**kw))


def get_setup_args(**kw):
    if 'plugins' in kw:
        py_modules = []
        for plg in kw['plugins']:
            py_modules.append("twisted.plugins." + plg)
        kw.setdefault('py_modules', []).extend(py_modules)
        del kw['plugins']

    if 'cmdclass' not in kw:
        kw['cmdclass'] = {'build_scripts': build_scripts_twisted}

    if "conditionalExtensions" in kw:
        extensions = kw["conditionalExtensions"]
        del kw["conditionalExtensions"]
    return kw


def getVersion(base):
    """
    Extract the version number.

    @rtype: str
    @returns: The version number of the project, as a string like
    "2.0.0".
    """
    vfile = os.path.join(base, '_version.py')
    ns = {'__name__': 'Nothing to see here'}
    execfile(vfile, ns)
    return ns['version'].base()


# Names that are excluded from globbing results:
EXCLUDE_NAMES = ["{arch}", "CVS", ".cvsignore", "_darcs",
                 "RCS", "SCCS", ".svn"]
EXCLUDE_PATTERNS = ["*.py[cdo]", "*.s[ol]", ".#*", "*~", "*.py", "*.cache",
                    "*.old"]


def _filterNames(names):
    """
    Given a list of file names, return those names that should be copied.
    """
    names = [n for n in names
             if n not in EXCLUDE_NAMES]
    # This is needed when building a distro from a working
    # copy (likely a checkout) rather than a pristine export:
    for pattern in EXCLUDE_PATTERNS:
        names = [n for n in names
                 if (not fnmatch.fnmatch(n, pattern))
                 and (not n.endswith('.py'))]
    return names


def relativeTo(base, relativee):
    """
    Gets 'relativee' relative to 'basepath'.

    i.e.,

    >>> relativeTo('/home/', '/home/radix/')
    'radix'
    >>> relativeTo('.', '/home/radix/Projects/Twisted') # curdir is /home/radix
    'Projects/Twisted'

    The 'relativee' must be a child of 'basepath'.
    """
    basepath = os.path.abspath(base)
    relativee = os.path.abspath(relativee)
    if relativee.startswith(basepath):
        relative = relativee[len(basepath):]
        if relative.startswith(os.sep):
            relative = relative[1:]
        return os.path.join(base, relative)
    raise ValueError("%s is not a subpath of %s" % (relativee, basepath))


def getExtensions():
    """
    Get the C extensions used for Twisted.
    """
    extensions = [
        ConditionalExtension(
            "twisted.test.raiser",
            ["twisted/test/raiser.c"],
            condition=lambda _: _isCPython),

        ConditionalExtension(
            "twisted.internet.iocpreactor.iocpsupport",
            ["twisted/internet/iocpreactor/iocpsupport/iocpsupport.c",
             "twisted/internet/iocpreactor/iocpsupport/winsock_pointers.c"],
            libraries=["ws2_32"],
            condition=lambda _: _isCPython and sys.platform == "win32"),

        ConditionalExtension(
            "twisted.python._sendmsg",
            sources=["twisted/python/_sendmsg.c"],
            condition=lambda _: sys.platform != "win32"),

        ConditionalExtension(
            "twisted.runner.portmap",
            ["twisted/runner/portmap.c"],
            condition=lambda builder: builder._check_header("rpc/rpc.h")),
    ]

    return extensions



def getScripts(basedir=''):
    """
    Returns a list of scripts for Twisted.
    """
    scriptdir = os.path.join(basedir, 'bin')
    if not os.path.isdir(scriptdir):
        # Probably a project-specific tarball, in which case only this
        # project's bins are included in 'bin'
        scriptdir = os.path.join(basedir, 'bin')
        if not os.path.isdir(scriptdir):
            return []
    thingies = os.listdir(scriptdir)
    for specialExclusion in ['.svn', '_preamble.py', '_preamble.pyc']:
        if specialExclusion in thingies:
            thingies.remove(specialExclusion)
    return filter(os.path.isfile,
                  [os.path.join(scriptdir, x) for x in thingies])


## Helpers and distutil tweaks

class build_scripts_twisted(build_scripts.build_scripts):
    """
    Renames scripts so they end with '.py' on Windows.
    """
    def run(self):
        build_scripts.build_scripts.run(self)
        if not os.name == "nt":
            return
        for f in os.listdir(self.build_dir):
            fpath = os.path.join(self.build_dir, f)
            if not fpath.endswith(".py"):
                pypath = fpath + ".py"
                if os.path.exists(pypath):
                    os.unlink(pypath)
                os.rename(fpath, pypath)


def _checkCPython(sys=sys, platform=platform):
    """
    Checks if this implementation is CPython.

    This uses C{platform.python_implementation}.

    This takes C{sys} and C{platform} kwargs that by default use the real
    modules. You shouldn't care about these -- they are for testing purposes
    only.

    @return: C{False} if the implementation is definitely not CPython, C{True}
        otherwise.
    """
    return platform.python_implementation() == "CPython"


_isCPython = _checkCPython()
