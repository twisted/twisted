# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""A kqueue()/kevent() based implementation of the Twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added)::

    | from twisted.internet import kqreactor
    | kqreactor.install()

This reactor only works on FreeBSD and requires PyKQueue 1.3, which is
available at:  U{http://people.freebsd.org/~dwhite/PyKQueue/}

API Stability: stable

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}



You're going to need to patch PyKqueue:

=====================================================
--- PyKQueue-1.3/kqsyscallmodule.c	Sun Jan 28 21:59:50 2001
+++ PyKQueue-1.3/kqsyscallmodule.c.new	Tue Jul 30 18:06:08 2002
@@ -137,7 +137,7 @@
 }
 
 statichere PyTypeObject KQEvent_Type = {
-  PyObject_HEAD_INIT(NULL)
+  PyObject_HEAD_INIT(&PyType_Type)
   0,                             // ob_size
   "KQEvent",                     // tp_name
   sizeof(KQEventObject),         // tp_basicsize
@@ -291,13 +291,14 @@
 
   /* Build timespec for timeout */
   totimespec.tv_sec = timeout / 1000;
-  totimespec.tv_nsec = (timeout % 1000) * 100000;
+  totimespec.tv_nsec = (timeout % 1000) * 1000000;
 
   // printf("timespec: sec=%d nsec=%d\n", totimespec.tv_sec, totimespec.tv_nsec);
 
   /* Make the call */
-
+  Py_BEGIN_ALLOW_THREADS
   gotNumEvents = kevent (self->fd, changelist, haveNumEvents, triggered, wantNumEvents, &totimespec);
+  Py_END_ALLOW_THREADS
 
   /* Don't need the input event list anymore, so get rid of it */
   free (changelist);
@@ -361,7 +362,7 @@
 statichere PyTypeObject KQueue_Type = {
 	/* The ob_type field must be initialized in the module init function
 	 * to be portable to Windows without using C++. */
-	PyObject_HEAD_INIT(NULL)
+	PyObject_HEAD_INIT(&PyType_Type)
 	0,			/*ob_size*/
 	"KQueue",			/*tp_name*/
 	sizeof(KQueueObject),	/*tp_basicsize*/

"""

# System imports
import errno, sys

# PyKQueue imports
from kqsyscall import *

# Twisted imports
from twisted.python import log, failure

# Sibling imports
import main
import default

# globals
reads = {}
writes = {}
selectables = {}
kq = kqueue()


class KQueueReactor(default.PosixReactorBase):
    """A reactor that uses kqueue(2)/kevent(2)."""

    def _updateRegistration(self, *args):
        kq.kevent([kevent(*args)], 0, 0)

    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read.
        """
        fd = reader.fileno()
        if not reads.has_key(fd):
            selectables[fd] = reader
            reads[fd] = 1
            self._updateRegistration(fd, EVFILT_READ, EV_ADD)

    def addWriter(self, writer, writes=writes, selectables=selectables):
        """Add a FileDescriptor for notification of data available to write.
        """
        fd = writer.fileno()
        if not writes.has_key(fd):
            selectables[fd] = writer
            writes[fd] = 1
            self._updateRegistration(fd, EVFILT_WRITE, EV_ADD)

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        fd = reader.fileno()
        if reads.has_key(fd):
            del reads[fd]
            if not writes.has_key(fd): del selectables[fd]
            self._updateRegistration(fd, EVFILT_READ, EV_DELETE)

    def removeWriter(self, writer, writes=writes):
        """Remove a Selectable for notification of data available to write.
        """
        fd = writer.fileno()
        if writes.has_key(fd):
            del writes[fd]
            if not reads.has_key(fd): del selectables[fd]
            self._updateRegistration(fd, EVFILT_WRITE, EV_DELETE)

    def removeAll(self):
        """Remove all selectables, and return a list of them."""
        result = selectables.values()
        for fd in reads.keys():
            self._updateRegistration(fd, EVFILT_READ, EV_DELETE)
        for fd in writes.keys():
            self._updateRegistration(fd, EVFILT_WRITE, EV_DELETE)
        reads.clear()
        writes.clear()
        selectables.clear()
        return result

    def doKEvent(self, timeout,
                 reads=reads,
                 writes=writes,
                 selectables=selectables,
                 kq=kq,
                 log=log,
                 OSError=OSError,
                 EVFILT_READ=EVFILT_READ,
                 EVFILT_WRITE=EVFILT_WRITE):
        """Poll the kqueue for new events."""
        if timeout is None:
            timeout = 1000
        else:
            timeout = int(timeout * 1000) # convert seconds to milliseconds

        try:
            l = kq.kevent([], len(selectables), timeout)
        except OSError, e:
            if e[0] == errno.EINTR:
                return
            else:
                raise
        _drdw = self._doWriteOrRead
        for event in l:
            why = None
            fd, filter = event.ident, event.filter
            selectable = selectables[fd]
            log.callWithLogger(selectable, _drdw, selectable, fd, filter)

    def _doWriteOrRead(self, selectable, fd, filter):
        try:
            if filter == EVFILT_READ:
                why = selectable.doRead()
            if filter == EVFILT_WRITE:
                why = selectable.doWrite()
            if not selectable.fileno() == fd:
                why = main.CONNECTION_LOST
        except:
            why = sys.exc_info()[1]
            log.deferr()

        if why:
            self.removeReader(selectable)
            self.removeWriter(selectable)
            selectable.connectionLost(failure.Failure(why))

    doIteration = doKEvent


def install():
    k = KQueueReactor()
    main.installReactor(k)


__all__ = ["KQueueReactor", "install"]
