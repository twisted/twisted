"""Test win32 postinstall script
"""

from pyunit import unittest

from twisted.scripts import postinstall
import os.path

def noop(name):
    pass

postinstall.directory_created=postinstall.file_created=noop

class PostinstallTest(unittest.TestCase):
    def testInstall(self):
        files=postinstall.install()
        for file in files:
            assert os.path.exists(file)

    def testRemove(self):
        assert postinstall.remove() is None
