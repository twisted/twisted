# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for POSIX-based L{IReactorProcess} implementations.
"""

import errno, os

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
                self.assertEqual(
                    errno.EBADF, err.errno,
                    "fcntl(%d, F_GETFL) failed with unexpected errno %d" % (
                        fd, err.errno))


    def test_expectedFDs(self):
        """
        L{_listOpenFDs} lists expected file descriptors.
        """
        # This is a tricky test.  A priori, there is no way to know what file
        # descriptors are open now, so there is no way to know what _listOpenFDs
        # should return.  Work around this by creating some new file descriptors
        # which we can know the state of and then just making assertions about
        # their presence or absence in the result.

        # Expect a file we just opened to be listed.
        f = file(os.devnull)
        openfds = process._listOpenFDs()
        self.assertIn(f.fileno(), openfds)

        # Expect a file we just closed not to be listed - with a caveat.  The
        # implementation may need to open a file to discover the result.  That
        # open file descriptor will be allocated the same number as the one we
        # just closed.  So, instead, create a hole in the file descriptor space
        # to catch that internal descriptor and make the assertion about a
        # different closed file descriptor.

        # This gets allocated a file descriptor larger than f's, since nothing
        # has been closed since we opened f.
        fd = os.dup(f.fileno())

        # But sanity check that; if it fails the test is invalid.
        self.assertTrue(
            fd > f.fileno(),
            "Expected duplicate file descriptor to be greater than original")

        try:
            # Get rid of the original, creating the hole.  The copy should still
            # be open, of course.
            f.close()
            self.assertIn(fd, process._listOpenFDs())
        finally:
            # Get rid of the copy now
            os.close(fd)
        # And it should not appear in the result.
        self.assertNotIn(fd, process._listOpenFDs())
