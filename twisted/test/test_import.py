# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.python.runtime import platformType


class AtLeastImportTestCase(unittest.TestCase):
    """
    I test that there are no syntax errors which will not allow importing.
    """

    failureException = ImportError

    def test_misc(self):
        """
        Test importing other miscellaneous modules.
        """
        from twisted import copyright

    def test_persisted(self):
        """
        Test importing persisted.
        """
        from twisted.persisted import dirdbm
        from twisted.persisted import styles

    def test_internet(self):
        """
        Test importing internet.
        """
        from twisted.internet import tcp
        from twisted.internet import main   
        from twisted.internet import abstract
        from twisted.internet import udp
        from twisted.internet import protocol
        from twisted.internet import defer

    def test_unix(self):
        """
        Test internet modules for unix.
        """
        from twisted.internet import stdio
        from twisted.internet import process
        from twisted.internet import unix

    if platformType != "posix":
        test_unix.skip = "UNIX-only modules"

    def test_spread(self):
        """
        Test importing spreadables.
        """
        from twisted.spread import pb
        from twisted.spread import jelly
        from twisted.spread import banana
        from twisted.spread import flavors

    def test_twistedPython(self):
        """
        Test importing C{twisted.python}.
        """
        from twisted.python import hook
        from twisted.python import log
        from twisted.python import reflect
        from twisted.python import usage
        from twisted.python import otp

    def test_protocols(self):
        """
        Test importing protocols.
        """
        from twisted.protocols import basic
        from twisted.protocols import ftp
        from twisted.protocols import telnet
        from twisted.protocols import policies
