from twisted.trial import unittest, util

import os
if os.name == 'posix':
    from twisted.python import lockfile
    import os.path

    class LockFileTest(unittest.TestCase):

        def testCreate(self):
            d = lockfile.createLock('test', usePID=1)
            lf = util.deferredResult(d)
            self.assertEquals(lf.filename, "test.lock")
            self.assert_(os.path.exists("test.lock"))
            data = int(open("test.lock").read())
            self.assertEquals(data, os.getpid())
            self.assert_(lockfile.checkLock('test'))
            lf.remove()
            self.assert_(not os.path.exists("test.lock"))
