import os
from twisted.trial import unittest, assertions as A

from twisted.python import release


class HappyTransaction(release.Transaction):
    def doIt(self, stuff):
        stuff.append(':-)')

class SadTransaction(release.Transaction):
    def doIt(self, stuff):
        raise release.CommandFailed(stuff)
    def undoIt(self, l, failure):
        l.append(failure.check(release.CommandFailed))


class TransactionTest(unittest.TestCase):
    def testHappy(self):
        l = ["hoo"]
        HappyTransaction().run(l)
        A.assertEquals(l, ["hoo", ":-)"])

    def testSad(self):
        l = []
        A.assertRaises(release._TransactionFailed,
                       SadTransaction().run, l)
        A.assertEquals(l, [release.CommandFailed])

    def testMultiple(self):
        l = []
        release.runTransactions([HappyTransaction, SadTransaction, HappyTransaction], l)
        A.assertEquals(l, [":-)", release.CommandFailed])



class UtilityTest(unittest.TestCase):
    def testChdir(self):
        cwd = os.getcwd()
        def chAndBreak():
            os.mkdir('releaseCh')
            os.chdir('releaseCh')
            1/0
        A.assertRaises(ZeroDivisionError,
                       release.runChdirSafe, chAndBreak)
        A.assertEquals(cwd, os.getcwd())

    def testReplaceInFile(self):
        in_ = 'foo\nhey hey $VER\nbar\n'
        outf = open('release.replace', 'w')
        outf.write(in_)
        outf.close()

        expected = in_.replace('$VER', '2.0.0')
        release.replaceInFile('release.replace', '$VER', '2.0.0')
        A.assertEquals(open('release.replace').read(), expected)

        expected = expected.replace('2.0.0', '3.0.0')
        release.replaceInFile('release.replace', '2.0.0', '3.0.0', True)
        A.assertEquals(open('release.replace').read(), expected)
