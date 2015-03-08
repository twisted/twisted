#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils installer for Twisted.
"""

try:
    # Load setuptools, to build a specific source package
    import setuptools
    # Tell Twisted not to enforce zope.interface requirement on import, since
    # we're going to have to import twisted.python.dist and can rely on
    # setuptools to install dependencies.
    setuptools._TWISTED_NO_CHECK_REQUIREMENTS = True
except ImportError:
    pass

import os
import sys


def main(args):
    """
    Invoke twisted.python.dist with the appropriate metadata about the
    Twisted package.
    """
    # On Python 3, use setup3.py until Python 3 port is done:
    if sys.version_info[0] > 2:
        import setup3
        setup3.main()
        return

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
        setup_args['include_package_data'] = True
        setup_args['zip_safe'] = False

    from twisted.python.dist import (
        STATIC_PACKAGE_METADATA, getDataFiles, getExtensions, getAllScripts,
        getPackages, setup, _EXTRAS_REQUIRE)

    scripts = getAllScripts()

    setup_args.update(dict(
        packages=getPackages('twisted'),
        conditionalExtensions=getExtensions(),
        scripts=scripts,
        extras_require=_EXTRAS_REQUIRE,
        data_files=getDataFiles('twisted'),
        **STATIC_PACKAGE_METADATA))

    setup(**setup_args)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)
