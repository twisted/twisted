# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for C{setup.py}, Twisted's distutils integration file.
"""

from __future__ import division, absolute_import

import os, sys

import twisted
from twisted.trial.unittest import SynchronousTestCase
from twisted.python.filepath import FilePath
from twisted.python.dist import getExtensions

# Get rid of the UTF-8 encoding and bytes topfiles segment when FilePath
# supports unicode.  #2366, #4736, #5203.  Also #4743, which requires checking
# setup.py, not just the topfiles directory.
if not FilePath(twisted.__file__.encode('utf-8')).sibling(b'topfiles').child(b'setup.py').exists():
    sourceSkip = "Only applies to source checkout of Twisted"
else:
    sourceSkip = None


class TwistedExtensionsTests(SynchronousTestCase):
    if sourceSkip is not None:
        skip = sourceSkip

    def setUp(self):
        """
        Change the working directory to the parent of the C{twisted} package so
        that L{twisted.python.dist.getExtensions} finds Twisted's own extension
        definitions.
        """
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(FilePath(twisted.__file__).parent().parent().path)


    def test_initgroups(self):
        """
        If C{os.initgroups} is present (Python 2.7 and Python 3.3 and newer),
        L{twisted.python._initgroups} is not returned as an extension to build
        from L{getExtensions}.
        """
        extensions = getExtensions()
        found = None
        for extension in extensions:
            if extension.name == "twisted.python._initgroups":
                found = extension

        if sys.version_info[:2] >= (2, 7):
            self.assertIdentical(
                None, found,
                "Should not have found twisted.python._initgroups extension "
                "definition.")
        else:
            self.assertNotIdentical(
                None, found,
                "Should have found twisted.python._initgroups extension "
                "definition.")
