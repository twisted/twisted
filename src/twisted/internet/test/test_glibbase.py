# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.internet.glibbase.
"""

from __future__ import division, absolute_import

import sys
from twisted.trial.unittest import TestCase
from twisted.internet._glibbase import ensureNotImported

try:
    from twisted.internet import gireactor
    from gi.repository import Gio
except ImportError:
    gireactor = None
    gtk3reactor = None
else:
    # gtk3reactor may be unavailable even if gireactor is available; in
    # particular in pygobject 3.4/gtk 3.6, when no X11 DISPLAY is found.
    try:
        from twisted.internet import gtk3reactor
    except ImportError:
        gtk3reactor = None
    else:
        from gi.repository import Gtk



class EnsureNotImportedTests(TestCase):
    """
    L{ensureNotImported} protects against unwanted past and future imports.
    """

    def test_ensureWhenNotImported(self):
        """
        If the specified modules have never been imported, and import
        prevention is requested, L{ensureNotImported} makes sure they will not
        be imported in the future.
        """
        modules = {}
        self.patch(sys, "modules", modules)
        ensureNotImported(["m1", "m2"], "A message.",
                          preventImports=["m1", "m2", "m3"])
        self.assertEqual(modules, {"m1": None, "m2": None, "m3": None})


    def test_ensureWhenNotImportedDontPrevent(self):
        """
        If the specified modules have never been imported, and import
        prevention is not requested, L{ensureNotImported} has no effect.
        """
        modules = {}
        self.patch(sys, "modules", modules)
        ensureNotImported(["m1", "m2"], "A message.")
        self.assertEqual(modules, {})


    def test_ensureWhenFailedToImport(self):
        """
        If the specified modules have been set to L{None} in C{sys.modules},
        L{ensureNotImported} does not complain.
        """
        modules = {"m2": None}
        self.patch(sys, "modules", modules)
        ensureNotImported(["m1", "m2"], "A message.", preventImports=["m1", "m2"])
        self.assertEqual(modules, {"m1": None, "m2": None})


    def test_ensureFailsWhenImported(self):
        """
        If one of the specified modules has been previously imported,
        L{ensureNotImported} raises an exception.
        """
        module = object()
        modules = {"m2": module}
        self.patch(sys, "modules", modules)
        e = self.assertRaises(ImportError, ensureNotImported,
                              ["m1", "m2"], "A message.",
                              preventImports=["m1", "m2"])
        self.assertEqual(modules, {"m2": module})
        self.assertEqual(e.args, ("A message.",))

class GlibReactorBaseTests(TestCase):

    def test_simulate(self):
        """

        """
        gireactor.install()
        reactor.simulate()
