import os
from twisted.trial import unittest

from twisted.internet import reactor
from twisted.python import release, log


class UtilityTest(unittest.TestCase):
    def test_chdir(self):
        """
        Test that the runChdirSafe is actually safe, i.e., it still
        changes back to the original directory even if an error is
        raised.
        """
        cwd = os.getcwd()
        def chAndBreak():
            os.mkdir('releaseCh')
            os.chdir('releaseCh')
            1/0
        self.assertRaises(ZeroDivisionError,
                          release.runChdirSafe, chAndBreak)
        self.assertEquals(cwd, os.getcwd())



    def test_replaceInFile(self):
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



class ProjectTest(unittest.TestCase):

    def test_fullyQualifiedNameCore(self):
        """
        Project's fullyQualifiedName should return "Twisted" when we
        ask for the project name for the "twisted" project.
        """
        self.assertEquals(release.Project(name="twisted").fullyQualifiedName(),
                          "Twisted")

    def test_fullyQualifiedNameOther(self):
        """
        Project's fullyQualifiedName should return "Twisted Blah" when we
        ask for the project name for the "blah" project.
        """
        self.assertEquals(release.Project(name="blah").fullyQualifiedName(),
                          "Twisted Blah")


class GetVersionTest(unittest.TestCase):
    def test_getVersionSafelyDontExplode(self):
        """
        When asking getVersionSafely for a nonsensical project name's
        version, return None.
        """
        self.assertEquals(release.getVersionSafely("This is a crappy project"),
                          None)


class VersionWritingTest(unittest.TestCase):
    def test_replaceProjectVersion(self):
        release.replaceProjectVersion("test_project", [0, 82, 7])
        ns = {'__name___': 'twisted.test_project'}
        execfile("test_project", ns)
        self.assertEquals(ns["version"].base(), "0.82.7")


