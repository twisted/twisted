"""
Test win32 shortcut script
"""

import os
import os.path

from twisted.trial import unittest

skipWindowsNopywin32 = None
try:
    from twisted.python import shortcut
except ImportError:
    skipWindowsNopywin32 = ("twisted.python.shortcut is only available "
                            "on Windows with win32com.")

class ShortcutTests(unittest.TestCase):
    def testCreate(self):
        s1=shortcut.Shortcut("test_shortcut.py")
        tempname=self.mktemp() + '.lnk'
        s1.save(tempname)
        self.assertTrue(os.path.exists(tempname))
        sc=shortcut.open(tempname)
        self.assertTrue(sc.GetPath(0)[0].endswith('test_shortcut.py'))
ShortcutTests.skip = skipWindowsNopywin32
