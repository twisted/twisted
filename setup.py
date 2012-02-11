#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils installer for Twisted.
"""

try:
    # Load setuptools, to build a specific source package
    import setuptools
except ImportError:
    pass

import sys, os


def getExtensions():
    """
    Get all extensions from core and all subprojects.
    """
    extensions = []

    if not sys.platform.startswith('java'):
        for dir in os.listdir("twisted") + [""]:
            topfiles = os.path.join("twisted", dir, "topfiles")
            if os.path.isdir(topfiles):
                ns = {}
                setup_py = os.path.join(topfiles, "setup.py")
                execfile(setup_py, ns, ns)
                if "extensions" in ns:
                    extensions.extend(ns["extensions"])

    return extensions


def main(args):
    """
    Invoke twisted.python.dist with the appropriate metadata about the
    Twisted package.
    """
    if os.path.exists('twisted'):
        sys.path.insert(0, '.')
    from twisted import copyright
    from twisted.python.dist import getDataFiles, getScripts, getPackages, \
                                    setup, twisted_subprojects

    # "" is included because core scripts are directly in bin/
    projects = [''] + [x for x in os.listdir('bin')
                       if os.path.isdir(os.path.join("bin", x))
                       and x in twisted_subprojects]

    scripts = []
    for i in projects:
        scripts.extend(getScripts(i))

    setup_args = dict(
        # metadata
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
        packages = getPackages('twisted'),
        conditionalExtensions = getExtensions(),
        scripts = scripts,
        data_files=getDataFiles('twisted'),
        classifiers=[
            "Programming Language :: Python :: 2.5",
            "Programming Language :: Python :: 2.6",
            "Programming Language :: Python :: 2.7",
            ])

    if 'setuptools' in sys.modules:
        from pkg_resources import parse_requirements
        requirements = ["zope.interface"]
        try:
            list(parse_requirements(requirements))
        except:
            print """You seem to be running a very old version of setuptools.
This version of setuptools has a bug parsing dependencies, so automatic
dependency resolution is disabled.
"""
        else:
            setup_args['install_requires'] = requirements
        setup_args['include_package_data'] = True
        setup_args['zip_safe'] = False
    setup(**setup_args)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)

