# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.python import lockfile

class LockingTestCase(unittest.TestCase):
    def testBasics(self):
        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        self.failUnless(lock.lock())
        self.failUnless(lock.clean)
        lock.unlock()
        self.failUnless(lock.lock())
        self.failUnless(lock.clean)
        lock.unlock()


    def testProtection(self):
        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        self.failUnless(lock.lock())
        self.failUnless(lock.clean)
        self.failIf(lock.lock())
        lock.unlock()


    def testBigLoop(self):
        lockf = self.mktemp()
        lock = lockfile.FilesystemLock(lockf)
        self.failUnless(lock.lock())
        for i in xrange(500):
            self.failIf(lock.lock())
        lock.unlock()


    def testIsLocked(self):
        lockf = self.mktemp()
        self.failIf(lockfile.isLocked(lockf))
        lock = lockfile.FilesystemLock(lockf)
        self.failUnless(lock.lock())
        self.failUnless(lockfile.isLocked(lockf))
        lock.unlock()
        self.failIf(lockfile.isLocked(lockf))

    # A multiprocess test would be good here, for the sake of
    # completeness.  However, it is fairly safe to rely on the
    # filesystem to provide the semantics we require.

