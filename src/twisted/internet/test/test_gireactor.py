# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
GObject Introspection reactor tests; i.e. `gireactor` module for gio/glib/gtk
integration.
"""


from unittest import skipIf

try:
    from gi.repository import Gio  # type: ignore[import]
except ImportError:
    giImported = False
    gtkVersion = None
else:
    giImported = True
    # If we can import Gio, we ought to be able to import our reactor.
    from os import environ

    from gi import get_required_version, require_version  # type: ignore[import]

    from twisted.internet import gireactor

    try:
        gtkVersion = get_required_version("Gtk")
        if gtkVersion is None:
            require_version("Gtk", environ.get("TWISTED_TEST_GTK_VERSION", "4.0"))
            gtkVersion = get_required_version("Gtk")
    except ValueError as ve:
        gtkVersion = str(ve)
    else:
        from gi.repository import Gtk

from twisted.internet.error import ReactorAlreadyRunning
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.trial.unittest import SkipTest, TestCase

# Skip all tests if gi is unavailable:
if not giImported:
    skip = "GObject Introspection `gi` module not importable"


class GApplicationRegistrationTests(ReactorBuilder, TestCase):
    """
    GtkApplication and GApplication are supported by
    L{twisted.internet.gtk3reactor} and L{twisted.internet.gireactor}.

    We inherit from L{ReactorBuilder} in order to use some of its
    reactor-running infrastructure, but don't need its test-creation
    functionality.
    """

    def runReactor(self, app, reactor):
        """
        Register the app, run the reactor, make sure app was activated, and
        that reactor was running, and that reactor can be stopped.
        """
        if not hasattr(app, "quit"):
            raise SkipTest("Version of PyGObject is too old.")

        result = []

        def stop():
            result.append("stopped")
            reactor.stop()

        def activate(widget):
            result.append("activated")
            reactor.callLater(0, stop)

        app.connect("activate", activate)

        # We want reactor.stop() to *always* stop the event loop, even if
        # someone has called hold() on the application and never done the
        # corresponding release() -- for more details see
        # http://developer.gnome.org/gio/unstable/GApplication.html.
        app.hold()

        reactor.registerGApplication(app)
        ReactorBuilder.runReactor(self, reactor)
        self.assertEqual(result, ["activated", "stopped"])

    def test_gApplicationActivate(self):
        """
        L{Gio.Application} instances can be registered with a gireactor.
        """
        reactor = gireactor.GIReactor(useGtk=False)
        self.addCleanup(self.unbuildReactor, reactor)
        app = Gio.Application(
            application_id="com.twistedmatrix.trial.gireactor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

        self.runReactor(app, reactor)

    @skipIf(
        ((gtkVersion is None) or (gtkVersion not in ("3.0", "4.0"))),
        f"Unknown GTK version: {repr(gtkVersion)}",
    )
    def test_gtkApplicationActivate(self):
        """
        L{Gtk.Application} instances can be registered with a gtk3reactor.
        """
        reactor = gireactor.GIReactor()
        self.addCleanup(self.unbuildReactor, reactor)
        app = Gtk.Application(
            application_id="com.twistedmatrix.trial.gtk3reactor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.runReactor(app, reactor)

    def test_portable(self):
        """
        L{gireactor.PortableGIReactor} doesn't support application
        registration at this time.
        """
        reactor = gireactor.PortableGIReactor()
        self.addCleanup(self.unbuildReactor, reactor)
        app = Gio.Application(
            application_id="com.twistedmatrix.trial.gireactor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.assertRaises(NotImplementedError, reactor.registerGApplication, app)

    def test_noQuit(self):
        """
        Older versions of PyGObject lack C{Application.quit}, and so won't
        allow registration.
        """
        reactor = gireactor.GIReactor(useGtk=False)
        self.addCleanup(self.unbuildReactor, reactor)
        # An app with no "quit" method:
        app = object()
        exc = self.assertRaises(RuntimeError, reactor.registerGApplication, app)
        self.assertTrue(exc.args[0].startswith("Application registration is not"))

    def test_cantRegisterAfterRun(self):
        """
        It is not possible to register a C{Application} after the reactor has
        already started.
        """
        reactor = gireactor.GIReactor(useGtk=False)
        self.addCleanup(self.unbuildReactor, reactor)
        app = Gio.Application(
            application_id="com.twistedmatrix.trial.gireactor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

        def tryRegister():
            exc = self.assertRaises(
                ReactorAlreadyRunning, reactor.registerGApplication, app
            )
            self.assertEqual(
                exc.args[0], "Can't register application after reactor was started."
            )
            reactor.stop()

        reactor.callLater(0, tryRegister)
        ReactorBuilder.runReactor(self, reactor)

    def test_cantRegisterTwice(self):
        """
        It is not possible to register more than one C{Application}.
        """
        reactor = gireactor.GIReactor(useGtk=False)
        self.addCleanup(self.unbuildReactor, reactor)
        app = Gio.Application(
            application_id="com.twistedmatrix.trial.gireactor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        reactor.registerGApplication(app)
        app2 = Gio.Application(
            application_id="com.twistedmatrix.trial.gireactor2",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        exc = self.assertRaises(RuntimeError, reactor.registerGApplication, app2)
        self.assertEqual(
            exc.args[0], "Can't register more than one application instance."
        )
