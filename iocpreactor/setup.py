#!/usr/bin/env python

from __future__ import absolute_import, division, print_function

import os, sys

from setuptools import setup, find_packages, Extension

if __name__ == "__main__":

    setup(
        name='iocpreactor',
        author='Twisted Matrix Laboratories',
        maintainer='Amber Brown',
        maintainer_email='hawkowl@twistedmatrix.com',
        url="https://github.com/twisted/iocpreactor",
        classifiers = [
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Operating System :: Microsoft :: Windows",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.3",
            "Programming Language :: Python :: 3.4",
            "Programming Language :: Python :: 3.5",
        ],
        ext_modules=[
            Extension(
                "iocpreactor._iocpsupport",
                sources=[
                    "src/iocpreactor/iocpsupport/iocpsupport.c",
                    "src/iocpreactor/iocpsupport/winsock_pointers.c"
                ],
                libraries=["ws2_32"])
        ],
        use_incremental=True,
        setup_requires=['incremental'],
        install_requires=['incremental', 'twisted', 'pypiwin32'],
        package_dir={"": "src"},
        packages=find_packages('src') + ["twisted.plugins"],
        package_data={
            "twisted": ["plugins/iocpreactor.py"]
        },
        license="MIT",
        zip_safe=False,
        include_package_data=True,
        description='Windows I/O Completion Ports reactor for Twisted.',
        long_description=open('README.rst').read(),
    )
