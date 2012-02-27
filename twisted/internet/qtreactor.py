# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module provides support for Twisted to be driven by the Qt mainloop.

In order to use this support, simply do the following::
    |  app = QApplication(sys.argv) # your code to init Qt
    |  import qt4reactor
    |  qt4reactor.install()

Alternatively:

    |  from twisted.application import reactors
    |  reactors.installReactor('qt4')

Then use L{twisted.internet} APIs as usual.  The other methods here are not
intended to be called directly.

If you don't instantiate a `QApplication` or `QCoreApplication` prior to
installing the reactor, a `QCoreApplication` will be constructed
by the reactor.  `QCoreApplication` does not require a GUI so trial testing
can occur normally.

Twisted can be initialized after `QApplication.exec_()` with a call to
`reactor.runReturn()`. Calling `reactor.stop()` will unhook Twisted but
leaves your Qt application running.
"""


import sys
import gc
from zope.interface import implements
from twisted.internet.interfaces import IReactorFDSet
from twisted.python import log
from twisted.internet import posixbase

from PySide.QtCore import QSocketNotifier, QObject, SIGNAL, QTimer, QCoreApplication
from PySide.QtCore import QEventLoop


class TwistedSocketNotifier(QObject):
    """
    Connection between an fd event and reader/writer callbacks.
    """

    def __init__(self, parent, reactor, watcher, socketType):
        QObject.__init__(self, parent)
        self.reactor = reactor
        self.watcher = watcher
        fd = watcher.fileno()
        self.notifier = QSocketNotifier(fd, socketType, parent)
        self.notifier.setEnabled(True)
        if socketType == QSocketNotifier.Read:
            self.fn = self.read
        else:
            self.fn = self.write
        self.connect(self.notifier, SIGNAL("activated(int)"), self.fn)


    def shutdown(self):
        self.notifier.setEnabled(False)
        self.disconnect(self.notifier, SIGNAL("activated(int)"), self.fn)
        self.fn = self.watcher = None
        self.notifier.deleteLater()
        self.deleteLater()


    def read(self, fd):
        if not self.watcher:
            return
        w = self.watcher
        # doRead can cause self.shutdown to be called so keep a reference to self.watcher
        def _read():
            #Don't call me again, until the data has been read
            self.notifier.setEnabled(False)
            why = None
            try:
                why = w.doRead()
                inRead = True
            except:
                inRead = False
                log.err()
                why = sys.exc_info()[1]
            if why:
                self.reactor._disconnectSelectable(w, why, inRead)
            elif self.watcher:
                self.notifier.setEnabled(True) # Re enable notification following sucessfull read
            self.reactor._iterate(fromqt=True)
        log.callWithLogger(w, _read)


    def write(self, sock):
        if not self.watcher:
            return
        w = self.watcher
        def _write():
            why = None
            self.notifier.setEnabled(False)

            try:
                why = w.doWrite()
            except:
                log.err()
                why = sys.exc_info()[1]
            if why:
                self.reactor._disconnectSelectable(w, why, False)
            elif self.watcher:
                self.notifier.setEnabled(True)
            self.reactor._iterate(fromqt=True)
        log.callWithLogger(w, _write)



class QtReactor(posixbase.PosixReactorBase):
    implements(IReactorFDSet)


    def __init__(self):
        self._reads = {}
        self._writes = {}
        self._notifiers = {}
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        QObject.connect(self._timer, SIGNAL("timeout()"), self.iterate)
        
        self.qApp = QCoreApplication.instance()
        self._ownApp=False
        if self.qApp is None:
            self.qApp=QCoreApplication([])
            self._ownApp=True
        self._blockApp = None
        posixbase.PosixReactorBase.__init__(self)


    def _add(self, xer, primary, type):
        """
        Private method for adding a descriptor from the event loop.

        It takes care of adding it if  new or modifying it if already added
        for another state (read -> read/write for example).
        """
        if xer not in primary:
            primary[xer] = TwistedSocketNotifier(None, self, xer, type)


    def addReader(self, reader):
        """
        Add a FileDescriptor for notification of data available to read.
        """
        self._add(reader, self._reads, QSocketNotifier.Read)


    def addWriter(self, writer):
        """
        Add a FileDescriptor for notification of data available to write.
        """
        self._add(writer, self._writes, QSocketNotifier.Write)


    def _remove(self, xer, primary):
        """
        Private method for removing a descriptor from the event loop.

        It does the inverse job of _add, and also add a check in case of the fd
        has gone away.
        """
        if xer in primary:
            notifier = primary.pop(xer)
            notifier.shutdown()


    def removeReader(self, reader):
        """
        Remove a Selectable for notification of data available to read.
        """
        self._remove(reader, self._reads)


    def removeWriter(self, writer):
        """
        Remove a Selectable for notification of data available to write.
        """
        self._remove(writer, self._writes)


    def removeAll(self):
        """
        Remove all selectables, and return a list of them.
        """
        rv = self._removeAll(self._reads, self._writes)
        return rv


    def getReaders(self):
        return self._reads.keys()


    def getWriters(self):
        return self._writes.keys()


    def callLater(self,howlong, *args, **kargs):
        rval = super(QtReactor,self).callLater(howlong, *args, **kargs)
        self.reactorInvocation()
        return rval


    def reactorInvocation(self):
        self._timer.stop()
        self._timer.setInterval(0)
        self._timer.start()


    def _iterate(self, delay=None, fromqt=False):
        """
        See twisted.internet.interfaces.IReactorCore.iterate.
        """
        self.runUntilCurrent()
        self.doIteration(delay, fromqt)


    iterate = _iterate


    def doIteration(self, delay=None, fromqt=False):
        """
        This method is called by a Qt timer or by network activity on
        a file descriptor.

        If called becuase of network activiy then control should not
        be handed back to Qt as this would cause recursion.
        """

        if not self.running and self._blockApp:
            self._blockApp.quit()

        self._timer.stop()
        delay = max(delay, 1)
        if not fromqt:
            self.qApp.processEvents(QEventLoop.AllEvents, delay * 1000)
        if self.timeout() is None:
            timeout = 0.1
        elif self.timeout() == 0:
            timeout = 0
        else:
            timeout = self.timeout()
        self._timer.setInterval(timeout * 1000)
        self._timer.start()


    def runReturn(self, installSignalHandlers=True):
        self.startRunning(installSignalHandlers=installSignalHandlers)
        self.reactorInvocation()


    def crash(self):
        log.msg('crash')
        super(QtReactor, self).crash()
        if self._blockApp:
            self._blockApp.quit()


    def run(self, installSignalHandlers=True):
        if self._ownApp:
            self._blockApp = self.qApp
        else:
            self._blockApp = QEventLoop()
        self.runReturn()
        self._blockApp.exec_()



def install():
    """
    Install the Qt reactor.
    """
    p = QtReactor()
    from twisted.internet.main import installReactor
    installReactor(p)

__all__ = ["install"]

