# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests to ensure all attributes of L{twisted.internet.gtkreactor} are 
deprecated.
"""

import sys

from twisted.trial.unittest import TestCase


class GtkReactorDeprecation(TestCase):
    """
    Tests to ensure all attributes of L{twisted.internet.gtkreactor} are 
    deprecated.
    """

    class StubGTK:
        class GDK:
            INPUT_READ = None
        def input_add(self, *params):
            pass

    class StubPyGTK:
        def require(self, something):
            pass

    def setUp(self):
        """
        Create a stub for the module 'gtk' if it does not exist, so that it can
        be imported without errors or warnings.
        """
        self.mods = sys.modules.copy()
        sys.modules['gtk'] = self.StubGTK()
        sys.modules['pygtk'] = self.StubPyGTK()


    def tearDown(self):
        """
        Return sys.modules to the way it was before the test.
        """
        sys.modules.clear()
        sys.modules.update(self.mods)


    def lookForDeprecationWarning(self, testmethod, attributeName):
        warningsShown = self.flushWarnings([testmethod])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            "twisted.internet.gtkreactor." + attributeName + " "
            "was deprecated in Twisted 10.1.0: All new applications should be "
            "written with gtk 2.x, which is supported by "
            "twisted.internet.gtk2reactor.")


    def test_gtkReactor(self):
        """
        Test deprecation of L{gtkreactor.GtkReactor}
        """
        from twisted.internet import gtkreactor
        gtkreactor.GtkReactor();
        self.lookForDeprecationWarning(self.test_gtkReactor, "GtkReactor")


    def test_portableGtkReactor(self):
        """
        Test deprecation of L{gtkreactor.GtkReactor}
        """
        from twisted.internet import gtkreactor
        gtkreactor.PortableGtkReactor()
        self.lookForDeprecationWarning(self.test_portableGtkReactor,
                                       "PortableGtkReactor")


    def test_install(self):
        """
        Test deprecation of L{gtkreactor.install}
        """
        from twisted.internet import gtkreactor
        self.assertRaises(AssertionError, gtkreactor.install)
        self.lookForDeprecationWarning(self.test_install, "install")


    def test_portableInstall(self):
        """
        Test deprecation of L{gtkreactor.portableInstall}
        """
        from twisted.internet import gtkreactor
        self.assertRaises(AssertionError, gtkreactor.portableInstall)
        self.lookForDeprecationWarning(self.test_portableInstall,
                                       "portableInstall")
