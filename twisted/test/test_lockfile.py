from twisted.trial import unittest, util

import os
if os.name == 'posix':
    from twisted.internet import reactor
    from twisted.python import lockfile
    import os.path

    class LockFileTest(unittest.TestCase):

        def testCreate(self):
            d = lockfile.createLock('test', reactor.callLater, usePID=1)
            lf = util.deferredResult(d)
            self.assertEquals(lf.filename, "test.lock")
            self.assert_(os.path.exists("test.lock"))
            data = int(open("test.lock").read())
            self.assertEquals(data, os.getpid())
            self.assert_(lockfile.checkLock('test'))
            lf.remove()
            self.assert_(not os.path.exists("test.lock"))
            self.assert_(not lockfile.checkLock('test'))

        def testWaiting(self):
            open("test2.lock","w").write('')
            d = lockfile.createLock('test2', reactor.callLater, retryTime=2)
            self.lockFile = []
            d.addCallback(lambda x,s=self:s.lockFile.append(x))
            reactor.callLater(0,lambda:os.remove("test2.lock"))
            self.runReactor(5,1)
            self.assert_(self.lockFile)
            self.lockFile[0].remove()
