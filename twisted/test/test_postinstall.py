"""Test win32 postinstall script
"""

from twisted.trial import unittest
import sys

import os

if os.name == 'nt':
    sys.path.insert(0, "win32")
    import twisted_postinstall
    sys.path.remove("win32")
    import os.path

    def noop(name):
        pass

    twisted_postinstall.directory_created=twisted_postinstall.file_created=noop

    class PostinstallTest(unittest.TestCase):
        def testInstall(self):
            stdout_save=sys.stdout
            output=open("install.stdout.txt", 'w')
            sys.stdout=output
            files=twisted_postinstall.install()
            sys.stdout=stdout_save
            output.close()
            for file in files:
                assert os.path.exists(file)

        def testRemove(self):
            assert twisted_postinstall.remove() is None
