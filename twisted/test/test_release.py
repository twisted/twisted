from twisted.trial import unittest, assertions as A

from twisted.python import release

class TransactionTest(unittest.TestCase):
    def testHappy(self):
        class MyT(release.Transaction):
            def doIt(self, stuff):
                return stuff + "1"
        A.assertEquals(MyT().run("hoo ha"), "hoo ha1")

    def testSad(self):
        l = []
        class MyT(release.Transaction):
            def doIt(self, stuff):
                raise release.CommandFailed(stuff)
            def undoIt(self, stuff, failure):
                l.append(failure.check(release.CommandFailed))
        MyT().run("hoo ha")
        self.assertEquals(l, [release.CommandFailed])
