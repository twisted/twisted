# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Dropin module defining all of the plugins provided by Twisted core.
"""

import warnings

from zope.interface import implements

from twisted.trial.itrial import IReporter
from twisted.plugin import IPlugin
from twisted.application.service import ServiceMaker
from twisted.application.reactors import Reactor, NoSuchReactor
from twisted.cred.strcred import ICheckerFactory, UNIXCheckerFactory, InMemoryCheckerFactory, FileCheckerFactory, AnonymousCheckerFactory


theUnixCheckerFactory = UNIXCheckerFactory()
theInMemoryCheckerFactory = InMemoryCheckerFactory()
theFileCheckerFactory = FileCheckerFactory()
theAnonymousCheckerFactory = AnonymousCheckerFactory()


class _Reporter(object):
    implements(IPlugin, IReporter)

    def __init__(self, name, module, description, longOpt, shortOpt, klass):
        self.name = name
        self.module = module
        self.description = description
        self.longOpt = longOpt
        self.shortOpt = shortOpt
        self.klass = klass


Tree = _Reporter("Tree Reporter",
                 "twisted.trial.reporter",
                 description="verbose color output (default reporter)",
                 longOpt="verbose",
                 shortOpt="v",
                 klass="TreeReporter")

BlackAndWhite = _Reporter("Black-And-White Reporter",
                          "twisted.trial.reporter",
                          description="Colorless verbose output",
                          longOpt="bwverbose",
                          shortOpt="o",
                          klass="VerboseTextReporter")

Minimal = _Reporter("Minimal Reporter",
                    "twisted.trial.reporter",
                    description="minimal summary output",
                    longOpt="summary",
                    shortOpt="s",
                    klass="MinimalReporter")

Classic = _Reporter("Classic Reporter",
                    "twisted.trial.reporter",
                    description="terse text output",
                    longOpt="text",
                    shortOpt="t",
                    klass="TextReporter")

Timing = _Reporter("Timing Reporter",
                   "twisted.trial.reporter",
                   description="Timing output",
                   longOpt="timing",
                   shortOpt=None,
                   klass="TimingTextReporter")


default = Reactor(
    'default', 'twisted.internet.default',
    'The best reactor for the current platform.')

select = Reactor(
    'select', 'twisted.internet.selectreactor', 'select(2)-based reactor.')
wx = Reactor(
    'wx', 'twisted.internet.wxreactor', 'wxPython integration reactor.')
gtk = Reactor(
    'gtk', 'twisted.internet.gtkreactor', 'Gtk1 integration reactor.')
gtk2 = Reactor(
    'gtk2', 'twisted.internet.gtk2reactor', 'Gtk2 integration reactor.')
glib2 = Reactor(
    'glib2', 'twisted.internet.glib2reactor',
    'GLib2 event-loop integration reactor.')
glade = Reactor(
    'debug-gui', 'twisted.manhole.gladereactor',
    'Semi-functional debugging/introspection reactor.')
win32er = Reactor(
    'win32', 'twisted.internet.win32eventreactor',
    'Win32 WaitForMultipleObjects-based reactor.')
poll = Reactor(
    'poll', 'twisted.internet.pollreactor', 'poll(2)-based reactor.')
epoll = Reactor(
    'epoll', 'twisted.internet.epollreactor', 'epoll(4)-based reactor.')
cf = Reactor(
    'cf' , 'twisted.internet.cfreactor',
    'CoreFoundation integration reactor.')
kqueue = Reactor(
    'kqueue', 'twisted.internet.kqreactor', 'kqueue(2)-based reactor.')
iocp = Reactor(
    'iocp', 'twisted.internet.iocpreactor',
    'Win32 IO Completion Ports-based reactor.')

wikiURL = 'http://twistedmatrix.com/trac/wiki/QTReactor'
errorMessage = ('qtreactor is no longer a part of Twisted due to licensing '
                'issues. Please see %s for details.' % (wikiURL,))

class QTStub(Reactor):
    """
    Reactor plugin which emits a deprecation warning on the successful
    installation of its reactor or a pointer to further information if an
    ImportError occurs while attempting to install it.
    """
    def __init__(self):
        super(QTStub, self).__init__(
            'qt', 'qtreactor', 'QT integration reactor')


    def install(self):
        """
        Install the Qt reactor with a deprecation warning or try to point
        the user to further information if it cannot be installed.
        """
        try:
            super(QTStub, self).install()
        except (ValueError, ImportError):
            raise NoSuchReactor(errorMessage)
        else:
            warnings.warn(
                "Please use -r qt3 to import qtreactor",
                category=DeprecationWarning)


qt = QTStub()


TwistedFTP = ServiceMaker(
    "Twisted FTP",
    "twisted.tap.ftp",
    "An FTP server.",
    "ftp")

TwistedPortForward = ServiceMaker(
    "Twisted Port-Forwarding",
    "twisted.tap.portforward",
    "A simple port-forwarder.",
    "portforward")

TwistedTelnet = ServiceMaker(
    "Twisted Telnet Shell Server",
    "twisted.tap.telnet",
    "A simple, telnet-based remote debugging service.",
    "telnet")

TwistedSOCKS = ServiceMaker(
    "Twisted SOCKS",
    "twisted.tap.socks",
    "A SOCKSv4 proxy service.",
    "socks")
