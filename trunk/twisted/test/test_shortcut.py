"""Test win32 shortcut script
"""

from twisted.trial import unittest

import os
if os.name == 'nt':

    skipWindowsNopywin32 = None
    try:
        from twisted.python import shortcut
    except ImportError:
        skipWindowsNopywin32 = ("On windows, twisted.python.shortcut is not "
                                "available in the absence of win32com.")
    import os.path
    import sys

    class ShortcutTest(unittest.TestCase):
        def testCreate(self):
            s1=shortcut.Shortcut("test_shortcut.py")
            tempname=self.mktemp() + '.lnk'
            s1.save(tempname)
            self.assert_(os.path.exists(tempname))
            sc=shortcut.open(tempname)
            self.assert_(sc.GetPath(0)[0].endswith('test_shortcut.py'))
    ShortcutTest.skip = skipWindowsNopywin32
