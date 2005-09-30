import os
from twisted.trial import unittest

from twisted.internet import reactor
from twisted.python import release, log


class UtilityTest(unittest.TestCase):
    def testChdir(self):
        cwd = os.getcwd()
        def chAndBreak():
            os.mkdir('releaseCh')
            os.chdir('releaseCh')
            1/0
        self.assertRaises(ZeroDivisionError,
                          release.runChdirSafe, chAndBreak)
        self.assertEquals(cwd, os.getcwd())

    def testReplaceInFile(self):
        in_ = 'foo\nhey hey $VER\nbar\n'
        outf = open('release.replace', 'w')
        outf.write(in_)
        outf.close()

        expected = in_.replace('$VER', '2.0.0')
        release.replaceInFile('release.replace', {'$VER': '2.0.0'})
        self.assertEquals(open('release.replace').read(), expected)


        expected = expected.replace('2.0.0', '3.0.0')
        release.replaceInFile('release.replace', {'2.0.0': '3.0.0'})
        self.assertEquals(open('release.replace').read(), expected)

