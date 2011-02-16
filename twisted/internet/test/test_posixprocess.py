# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for POSIX-based L{IReactorProcess} implementations.
"""

import errno, os, sys

try:
    import fcntl
except ImportError:
    platformSkip = "non-POSIX platform"
else:
    from twisted.internet import process
    platformSkip = None

from twisted.trial.unittest import TestCase


class FileDescriptorTests(TestCase):
    """
    Tests for L{twisted.internet.process._listOpenFDs}
    """
    skip = platformSkip

    def test_openFDs(self):
        """
        File descriptors returned by L{_listOpenFDs} are mostly open.

        This test assumes that zero-legth writes fail with EBADF on closed
        file descriptors.
        """
        for fd in process._listOpenFDs():
            try:
                fcntl.fcntl(fd, fcntl.F_GETFL)
            except IOError, err:
                self.assertEquals(
                    errno.EBADF, err.errno,
                    "fcntl(%d, F_GETFL) failed with unexpected errno %d" % (
                        fd, err.errno))


    def test_expectedFDs(self):
        """
        L{_listOpenFDs} lists expected file descriptors.
        """
        openfds = process._listOpenFDs()
        for f in sys.stdin, sys.stdout, sys.stderr:
            self.assertIn(f.fileno(), openfds)

        # See http://twistedmatrix.com/trac/ticket/4522#comment:17
        f = file(os.devnull)
        fd = os.dup(f.fileno())
        try:
            f.close()
            self.assertIn(fd, process._listOpenFDs())
        finally:
            os.close(fd)
        self.assertNotIn(fd, process._listOpenFDs())
