import os
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


class UtilityTest(unittest.TestCase):
    def testChdir(self):
        cwd = os.getcwd()
        def chAndBreak():
            os.mkdir('releaseCh')
            os.chdir('releaseCh')
        release.runChdirSafe(chAndBreak)
        self.assertEquals(cwd, os.getcwd())

    def testReplaceInFile(self):
        in_ = 'foo\nhey hey $VER\nbar'
        outf = open('release.replace', 'w')
        outf.write(in_)
        outf.close()
        
        expected = in_.replace('$VER', '2.0.0')
        release.replaceInFile('release.replace', '$VER', '2.0.0')
        self.assertEquals(open('release.replace').read(), expected)

        expected = expected.replace('2.0.0', '3.0.0')
        release.replaceInFile('release.replace', '2.0.0', '3.0.0', True)
        self.assertEquals(open('release.replace').read(), expected)
