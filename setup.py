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

import os
import sys


def main(args):
    """
    Invoke twisted.python.dist with the appropriate metadata about the
    Twisted package.
    """
    if os.path.exists('twisted'):
        sys.path.insert(0, '.')

    setup_args = {}

    if 'setuptools' in sys.modules:
        from pkg_resources import parse_requirements
        requirements = ["zope.interface >= 3.6.0"]
        try:
            list(parse_requirements(requirements))
        except:
            print("""You seem to be running a very old version of setuptools.
This version of setuptools has a bug parsing dependencies, so automatic
dependency resolution is disabled.
""")
        else:
            setup_args['install_requires'] = requirements
            setuptools._TWISTED_NO_CHECK_REQUIREMENTS = True
        setup_args['include_package_data'] = True
        setup_args['zip_safe'] = False

    from twisted.python.dist import (
        STATIC_PACKAGE_METADATA, getDataFiles, getExtensions, getAllScripts,
        getPackages, setup)

    scripts = getAllScripts()

    setup_args.update(dict(
        packages=getPackages('twisted'),
        conditionalExtensions=getExtensions(),
        scripts=scripts,
        data_files=getDataFiles('twisted'),
        **STATIC_PACKAGE_METADATA))

    setup(**setup_args)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)
