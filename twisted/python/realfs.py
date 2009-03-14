# -*- test-case-name: twisted.python.test.test_memfs -*-

"""
This module organizes Python's standard library functionality, from the
__builtin__, os, stat, and os.path modules, into a single interface so that it
can be easily parameterized.

It is currently incomplete; it should be filled in on an as-needed basis as we
need to test other filesystem APIs.
"""

from zope.interface import Interface, moduleProvides

import os

open = open
fsync = os.fsync
rename = os.rename

class IFileSystem(Interface):
    """
    Standard library functionality.
    """

    def open():
        """
        @see: os.open
        """


    def fsync():
        """
        @see: os.fsync
        """


    def rename():
        """
        @see: os.rename
        """



moduleProvides(IFileSystem)

__all__ = ['open', 'fsync']
