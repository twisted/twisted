import os

from twisted.trial import unittest

from twisted.python import dist



class GetVersionTest(unittest.TestCase):
    def setUp(self):
        self.dirname = self.mktemp()
        os.mkdir(self.dirname)

    def test_getVersionCore(self):
        """
        Test that getting the version of core reads from the
        [base]/_version.py file.
        """
        f = open(os.path.join(self.dirname, "_version.py"), "w")
        f.write("""
from twisted.python import versions
version = versions.Version("twisted", 0, 1, 2)
""")
        f.close()
        self.assertEquals(dist.getVersion("core", base=self.dirname), "0.1.2")

    def test_getVersionOther(self):
        """
        Test that getting the version of a non-core project reads from
        the [base]/[projname]/_version.py file.
        """
        os.mkdir(os.path.join(self.dirname, "blat"))
        f = open(os.path.join(self.dirname, "blat", "_version.py"), "w")
        f.write("""
from twisted.python import versions
version = versions.Version("twisted.blat", 9, 8, 10)
""")
        f.close()
        self.assertEquals(dist.getVersion("blat", base=self.dirname), "9.8.10")


class GetScriptsTest(unittest.TestCase):

    def test_scriptsInSVN(self):
        """
        getScripts should return the scripts associated with a project
        in the context of Twisted SVN.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        os.mkdir(os.path.join(basedir, 'bin', 'proj'))
        f = open(os.path.join(basedir, 'bin', 'proj', 'exy'), 'w')
        f.write('yay')
        f.close()
        scripts = dist.getScripts('proj', basedir=basedir)
        self.assertEquals(len(scripts), 1)
        self.assertEquals(os.path.basename(scripts[0]), 'exy')


    def test_scriptsInRelease(self):
        """
        getScripts should return the scripts associated with a project
        in the context of a released subproject tarball.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        f = open(os.path.join(basedir, 'bin', 'exy'), 'w')
        f.write('yay')
        f.close()
        scripts = dist.getScripts('proj', basedir=basedir)
        self.assertEquals(len(scripts), 1)
        self.assertEquals(os.path.basename(scripts[0]), 'exy')


    def test_noScriptsInSVN(self):
        """
        When calling getScripts for a project which doesn't actually
        have any scripts, in the context of an SVN checkout, an
        empty list should be returned.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        os.mkdir(os.path.join(basedir, 'bin', 'otherproj'))
        scripts = dist.getScripts('noscripts', basedir=basedir)
        self.assertEquals(scripts, [])


    def test_noScriptsInSubproject(self):
        """
        When calling getScripts for a project which doesn't actually
        have any scripts in the context of that project's individual
        project structure, an empty list should be returned.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        scripts = dist.getScripts('noscripts', basedir=basedir)
        self.assertEquals(scripts, [])
