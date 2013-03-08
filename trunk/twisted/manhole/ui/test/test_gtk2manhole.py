# Copyright (c) 2009 Twisted Matrix Laboratories.
"""
Tests for GTK2 GUI manhole.
"""

skip = False

try:
    import pygtk
    pygtk.require("2.0")
except:
    skip = "GTK 2.0 not available"
else:
    try:
        import gtk
    except ImportError:
        skip = "GTK 2.0 not available"
    except RuntimeError:
        skip = "Old version of GTK 2.0 requires DISPLAY, and we don't have one."
    else:
        if gtk.gtk_version[0] == 1:
            skip = "Requested GTK 2.0, but 1.0 was already imported."
        else:
            from twisted.manhole.ui.gtk2manhole import ConsoleInput

from twisted.trial.unittest import TestCase

from twisted.python.reflect import prefixedMethodNames

class ConsoleInputTests(TestCase):
    """
    Tests for L{ConsoleInput}.
    """

    def test_reverseKeymap(self):
        """
        Verify that a L{ConsoleInput} has a reverse mapping of the keysym names
        it needs for event handling to their corresponding keysym.
        """
        ci = ConsoleInput(None)
        for eventName in prefixedMethodNames(ConsoleInput, 'key_'):
            keysymName = eventName.split("_")[-1]
            keysymValue = getattr(gtk.keysyms, keysymName)
            self.assertEqual(ci.rkeymap[keysymValue], keysymName)


    skip = skip

