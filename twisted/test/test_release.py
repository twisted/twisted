import os
from twisted.trial import unittest, assertions as A

from twisted.python import release


class HappyTransaction(release.Transaction):
    def doIt(self, stuff):
        stuff.append(':-)')
        return stuff

class SadTransaction(release.Transaction):
    def doIt(self, stuff):
        raise release.CommandFailed(stuff)
    def undoIt(self, l, failure):
        l.append(failure.check(release.CommandFailed))
        return l


class TransactionTest(unittest.TestCase):
    def testHappy(self):
        A.assertEquals(HappyTransaction().run(["hoo"]), ["hoo", ":-)"])

    def testSad(self):
        l = []
        SadTransaction().run(l)
        self.assertEquals(l, [release.CommandFailed])

    def testMultiple(self):
        l = []
        release.runTransactions([HappyTransaction, SadTransaction], l)
        self.assertEquals(l, [":-)", release.CommandFailed])


class UtilityTest(unittest.TestCase):
    def testChdir(self):
        cwd = os.getcwd()
        def chAndBreak():
            os.mkdir('releaseCh')
            os.chdir('releaseCh')
            1/0
        try:
            release.runChdirSafe(chAndBreak)
        except ZeroDivisionError:
            A.assertEquals(cwd, os.getcwd())
        else:
            A.fail("Didn't raise ZeroDivisionError!?")

    def testReplaceInFile(self):
        in_ = 'foo\nhey hey $VER\nbar'
        outf = open('release.replace', 'w')
        outf.write(in_)
        outf.close()

        expected = in_.replace('$VER', '2.0.0')
        release.replaceInFile('release.replace', '$VER', '2.0.0')
        A.assertEquals(open('release.replace').read(), expected)

        expected = expected.replace('2.0.0', '3.0.0')
        release.replaceInFile('release.replace', '2.0.0', '3.0.0', True)
        A.assertEquals(open('release.replace').read(), expected)
