"""
Test win32 shortcut script
"""

import os.path
import sys
import tempfile

from twisted.python.runtime import platform
from twisted.trial import unittest

skipReason = None
if platform.isWindows():
    try:
        from twisted.python import shortcut
    except ImportError:
        skipReason = ("On Windows, twisted.python.shortcut is not "
                      "available in the absence of win32com.")
else:
    skipReason = "Only runs on Windows"



class ShortcutTests(unittest.TestCase):
    skip = skipReason

    def test_create(self):
        """
        Create a simple shortcut.
        """
        testFilename = __file__
        s1 = shortcut.Shortcut(testFilename)
        tempname = self.mktemp() + '.lnk'
        s1.save(tempname)
        self.assertTrue(os.path.exists(tempname))
        sc = shortcut.open(tempname)
        self.assertTrue(sc.GetPath(0)[0].endswith('test_shortcut.py'))


    def test_createPythonShortcut(self):
        """
        Create a shortcut to the Python executable,
        and set some values.
        """
        testFilename = sys.executable
        tempDir = tempfile.gettempdir()
        s1 = shortcut.Shortcut(path=testFilename,
                               arguments="-V",
                               description="The Python executable",
			       workingdir=tempDir,
			       iconpath=tempDir,
                               iconidx=1)
        tempname = self.mktemp() + '.lnk'
        s1.save(tempname)
        self.assertTrue(os.path.exists(tempname))
        sc = shortcut.open(tempname)
        self.assertTrue(sc.GetPath(0)[0].endswith(
            os.path.basename(sys.executable)))
        self.assertEqual(sc.GetDescription(), "The Python executable")
        self.assertEqual(sc.GetWorkingDirectory(), tempDir)
        self.assertEqual(sc.GetIconLocation(), (tempDir, 1))
