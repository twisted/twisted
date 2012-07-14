# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.unix}.
"""

import os

from twisted.conch.unix import mkOpenFlags
from twisted.conch.ssh.filetransfer import (FXF_READ, FXF_WRITE, FXF_APPEND,
                                            FXF_CREAT, FXF_TRUNC, FXF_EXCL)
from twisted.trial.unittest import TestCase



class MkOpenFlagsTest(TestCase):
    """
    L{twisted.conch.unix.mkOpenFlags} converts Conch constants into C{os}
    constants.
    """

    def _testFlag(self, flag, os_flag):
        """
        L{mkOpenFlags} converts the given C{sftp_flag} to C{os_flag}.

        Additionally, when ORed with FXF_APPEND, FXF_CREAT, FXF_TRUNC or
        FXF_EXCL, the corresponding OR takes place on the C{os} module flag.
        """
        result = mkOpenFlags(flag)
        self.assertEqual(result, os_flag)

        result = mkOpenFlags(flag | FXF_APPEND)
        self.assertEqual(result, os_flag | os.O_APPEND)

        result = mkOpenFlags(flag | FXF_CREAT)
        self.assertEqual(result, os_flag | os.O_CREAT)

        result = mkOpenFlags(flag | FXF_TRUNC)
        self.assertEqual(result, os_flag | os.O_TRUNC)

        result = mkOpenFlags(flag | FXF_EXCL)
        self.assertEqual(result, os_flag | os.O_EXCL)


    def test_FXF_READ(self):
        """
        L{mkOpenFlags} converts C{FXF_READ} into C{os.O_RDONLY}.
        """
        self._testFlag(FXF_READ, os.O_RDONLY)


    def test_FXF_WRITE(self):
        """
        L{mkOpenFlags} converts C{FXF_WRITE} into C{os.O_WRONLY}.
        """
        self._testFlag(FXF_WRITE, os.O_WRONLY)


    def test_FXF_READ_or_FXF_WRITE(self):
        """
        L{mkOpenFlags} converts C{FXF_READ | FXF_WRITE} into C{os.O_RDWR}.
        """
        self._testFlag(FXF_READ | FXF_WRITE, os.O_RDWR)
