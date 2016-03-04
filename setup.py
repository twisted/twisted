#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Setuptools installer for Twisted.
"""

import os
import sys
import setuptools

# Tell Twisted not to enforce zope.interface requirement on import, since
# we're going to have to import twisted.python.dist and can rely on
# setuptools to install dependencies.
setuptools._TWISTED_NO_CHECK_REQUIREMENTS = True


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

    requirements = ["zope.interface >= 3.6.0"]

    from twisted.python.dist import (
        STATIC_PACKAGE_METADATA, getExtensions, getScripts,
        setup, _EXTRAS_REQUIRE)

    setup_args = STATIC_PACKAGE_METADATA.copy()

    setup_args.update(dict(
        packages=setuptools.find_packages(),
        install_requires=requirements,
        conditionalExtensions=getExtensions(),
        scripts=getScripts(),
        include_package_data=True,
        zip_safe=False,
        extras_require=_EXTRAS_REQUIRE,
    ))

    setup(**setup_args)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)
