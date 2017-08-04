"""
Test win32 shortcut script
"""

import os.path

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

    def testCreate(self):
        s1=shortcut.Shortcut("test_shortcut.py")
        tempname=self.mktemp() + '.lnk'
        s1.save(tempname)
        self.assertTrue(os.path.exists(tempname))
        sc=shortcut.open(tempname)
        self.assertTrue(sc.GetPath(0)[0].endswith('test_shortcut.py'))
