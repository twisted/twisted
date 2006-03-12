# -*- test-case-name: twisted.test.test_internet -*-
# $Id: default.py,v 1.90 2004/01/06 22:35:22 warner Exp $
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Select reactor

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

from time import sleep
import sys

from zope.interface import implements

from twisted.internet.interfaces import IReactorFDSet
from twisted.internet import error
from twisted.internet import posixbase
from twisted.python import log, components
from twisted.persisted import styles
from twisted.python.runtime import platformType

import select
from errno import EINTR, EBADF

# global state for selector
reads = {}
writes = {}


def win32select(r, w, e, timeout=None):
    """Win32 select wrapper."""
    if not (r or w):
        # windows select() exits immediately when no sockets
        if timeout is None:
            timeout = 0.01
        else:
            timeout = min(timeout, 0.001)
        sleep(timeout)
        return [], [], []
    # windows doesn't process 'signals' inside select(), so we set a max
    # time or ctrl-c will never be recognized
    if timeout is None or timeout > 0.5:
        timeout = 0.5
    r, w, e = select.select(r, w, w, timeout)
    return r, w + e, []

if platformType == "win32":
    _select = win32select
else:
    _select = select.select

# Exceptions that doSelect might return frequently
_NO_FILENO = error.ConnectionFdescWentAway('Handler has no fileno method')
_NO_FILEDESC = error.ConnectionFdescWentAway('Filedescriptor went away')

class SelectReactor(posixbase.PosixReactorBase):
    """A select() based reactor - runs on all POSIX platforms and on Win32.
    """
    implements(IReactorFDSet)

    def _preenDescriptors(self):
        log.msg("Malformed file descriptor found.  Preening lists.")
        readers = reads.keys()
        writers = writes.keys()
        reads.clear()
        writes.clear()
        for selDict, selList in ((reads, readers), (writes, writers)):
            for selectable in selList:
                try:
                    select.select([selectable], [selectable], [selectable], 0)
                except:
                    log.msg("bad descriptor %s" % selectable)
                else:
                    selDict[selectable] = 1


    def doSelect(self, timeout,
                 # Since this loop should really be as fast as possible,
                 # I'm caching these global attributes so the interpreter
                 # will hit them in the local namespace.
                 reads=reads,
                 writes=writes):
        """Run one iteration of the I/O monitor loop.

        This will run all selectables who had input or output readiness
        waiting for them.
        """
        while 1:
            try:
                r, w, ignored = _select(reads.keys(),
                                        writes.keys(),
                                        [], timeout)
                break
            except ValueError, ve:
                # Possibly a file descriptor has gone negative?
                log.err()
                self._preenDescriptors()
            except TypeError, te:
                # Something *totally* invalid (object w/o fileno, non-integral
                # result) was passed
                log.err()
                self._preenDescriptors()
            except (select.error, IOError), se:
                # select(2) encountered an error
                if se.args[0] in (0, 2):
                    # windows does this if it got an empty list
                    if (not reads) and (not writes):
                        return
                    else:
                        raise
                elif se.args[0] == EINTR:
                    return
                elif se.args[0] == EBADF:
                    self._preenDescriptors()
                else:
                    # OK, I really don't know what's going on.  Blow up.
                    raise
        _drdw = self._doReadOrWrite
        _logrun = log.callWithLogger
        for selectables, method, dict in ((r, "doRead", reads),
                                          (w,"doWrite", writes)):
            hkm = dict.has_key
            for selectable in selectables:
                # if this was disconnected in another thread, kill it.
                if not hkm(selectable):
                    continue
                # This for pausing input when we're not ready for more.
                _logrun(selectable, _drdw, selectable, method, dict)

    doIteration = doSelect

    def _doReadOrWrite(self, selectable, method, dict):
        try:
            why = getattr(selectable, method)()
            handfn = getattr(selectable, 'fileno', None)
            if not handfn:
                why = _NO_FILENO
            elif handfn() == -1:
                why = _NO_FILEDESC
        except:
            why = sys.exc_info()[1]
            log.err()
        if why:
            self._disconnectSelectable(selectable, why, method=="doRead")
    
    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read.
        """
        reads[reader] = 1

    def addWriter(self, writer):
        """Add a FileDescriptor for notification of data available to write.
        """
        writes[writer] = 1

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        if reads.has_key(reader):
            del reads[reader]

    def removeWriter(self, writer):
        """Remove a Selectable for notification of data available to write.
        """
        if writes.has_key(writer):
            del writes[writer]

    def removeAll(self):
        return self._removeAll(reads, writes)
    

def install():
    """Configure the twisted mainloop to be run using the select() reactor.
    """
    reactor = SelectReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)

__all__ = ['install']
