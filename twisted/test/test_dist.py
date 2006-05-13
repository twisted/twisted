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
