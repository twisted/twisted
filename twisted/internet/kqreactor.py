# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A kqueue()/kevent() based implementation of the Twisted main loop.

To install the event loop (and you should do this before any connections,
listeners or connectors are added)::

    | from twisted.internet import kqreactor
    | kqreactor.install()

This reactor only works on FreeBSD and requires PyKQueue 1.3, which is
available at:  U{http://people.freebsd.org/~dwhite/PyKQueue/}



You're going to need to patch PyKqueue::

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
     
       // printf("timespec: sec=%d nsec=%d\\n", totimespec.tv_sec, totimespec.tv_nsec);
     
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

import errno, sys

from zope.interface import implements

from kqsyscall import EVFILT_READ, EVFILT_WRITE, EV_DELETE, EV_ADD
from kqsyscall import kqueue, kevent

from twisted.internet.interfaces import IReactorFDSet

from twisted.python import log, failure
from twisted.internet import main, posixbase


class KQueueReactor(posixbase.PosixReactorBase):
    """
    A reactor that uses kqueue(2)/kevent(2).

    @ivar _kq: A L{kqueue} which will be used to check for I/O readiness.

    @ivar _selectables: A dictionary mapping integer file descriptors to
        instances of L{FileDescriptor} which have been registered with the
        reactor.  All L{FileDescriptors} which are currently receiving read or
        write readiness notifications will be present as values in this
        dictionary.

    @ivar _reads: A dictionary mapping integer file descriptors to arbitrary
        values (this is essentially a set).  Keys in this dictionary will be
        registered with C{_kq} for read readiness notifications which will be
        dispatched to the corresponding L{FileDescriptor} instances in
        C{_selectables}.

    @ivar _writes: A dictionary mapping integer file descriptors to arbitrary
        values (this is essentially a set).  Keys in this dictionary will be
        registered with C{_kq} for write readiness notifications which will be
        dispatched to the corresponding L{FileDescriptor} instances in
        C{_selectables}.
    """
    implements(IReactorFDSet)

    def __init__(self):
        """
        Initialize kqueue object, file descriptor tracking dictionaries, and the
        base class.
        """
        self._kq = kqueue()
        self._reads = {}
        self._writes = {}
        self._selectables = {}
        posixbase.PosixReactorBase.__init__(self)


    def _updateRegistration(self, *args):
        self._kq.kevent([kevent(*args)], 0, 0)

    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read.
        """
        fd = reader.fileno()
        if fd not in self._reads:
            self._selectables[fd] = reader
            self._reads[fd] = 1
            self._updateRegistration(fd, EVFILT_READ, EV_ADD)

    def addWriter(self, writer):
        """Add a FileDescriptor for notification of data available to write.
        """
        fd = writer.fileno()
        if fd not in self._writes:
            self._selectables[fd] = writer
            self._writes[fd] = 1
            self._updateRegistration(fd, EVFILT_WRITE, EV_ADD)

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        fd = reader.fileno()
        if fd in self._reads:
            del self._reads[fd]
            if fd not in self._writes:
                del self._selectables[fd]
            self._updateRegistration(fd, EVFILT_READ, EV_DELETE)

    def removeWriter(self, writer):
        """Remove a Selectable for notification of data available to write.
        """
        fd = writer.fileno()
        if fd in self._writes:
            del self._writes[fd]
            if fd not in self._reads:
                del self._selectables[fd]
            self._updateRegistration(fd, EVFILT_WRITE, EV_DELETE)

    def removeAll(self):
        """
        Remove all selectables, and return a list of them.
        """
        return self._removeAll(
            [self._selectables[fd] for fd in self._reads],
            [self._selectables[fd] for fd in self._writes])


    def getReaders(self):
        return [self._selectables[fd] for fd in self._reads]


    def getWriters(self):
        return [self._selectables[fd] for fd in self._writes]


    def doKEvent(self, timeout):
        """Poll the kqueue for new events."""
        if timeout is None:
            timeout = 1000
        else:
            timeout = int(timeout * 1000) # convert seconds to milliseconds

        try:
            l = self._kq.kevent([], len(self._selectables), timeout)
        except OSError, e:
            if e[0] == errno.EINTR:
                return
            else:
                raise
        _drdw = self._doWriteOrRead
        for event in l:
            why = None
            fd, filter = event.ident, event.filter
            try:
                selectable = self._selectables[fd]
            except KeyError:
                # Handles the infrequent case where one selectable's
                # handler disconnects another.
                continue
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
