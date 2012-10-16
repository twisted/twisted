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


def main(args):
    """
    Invoke twisted.python.dist with the appropriate metadata about the
    Twisted package.
    """
    if os.path.exists('twisted'):
        sys.path.insert(0, '.')
    from twisted.python.dist import (
        STATIC_PACKAGE_METADATA, getDataFiles, getExtensions, getAllScripts,
        getPackages, setup)

    scripts = getAllScripts()

    setup_args = dict(
        packages=getPackages('twisted'),
        conditionalExtensions=getExtensions(),
        scripts=scripts,
        data_files=getDataFiles('twisted'),
        **STATIC_PACKAGE_METADATA
        )

    if 'setuptools' in sys.modules:
        from pkg_resources import parse_requirements
        requirements = ["zope.interface"]
        try:
            list(parse_requirements(requirements))
        except:
            print("""You seem to be running a very old version of setuptools.
This version of setuptools has a bug parsing dependencies, so automatic
dependency resolution is disabled.
""")
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

