# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interface to epoll I/O event notification facility.
"""

# NOTE: The version of Pyrex you are using probably _does not work_ with
# Python 2.5.  If you need to recompile this file, _make sure you are using
# a version of Pyrex which works with Python 2.5_.  I am using 0.9.4.1 from
# <http://codespeak.net/svn/lxml/pyrex/>. -exarkun

cdef extern from "stdio.h":
    cdef extern void *malloc(int)
    cdef extern void free(void *)
    cdef extern int close(int)

cdef extern from "errno.h":
    cdef extern int errno
    cdef extern char *strerror(int)

cdef extern from "string.h":
    cdef extern void *memset(void* s, int c, int n)

cdef extern from "stdint.h":
    ctypedef unsigned long uint32_t
    ctypedef unsigned long long uint64_t

cdef extern from "sys/epoll.h":

    cdef enum:
        EPOLL_CTL_ADD = 1
        EPOLL_CTL_DEL = 2
        EPOLL_CTL_MOD = 3

    cdef enum EPOLL_EVENTS:
        c_EPOLLIN "EPOLLIN" = 0x001
        c_EPOLLPRI "EPOLLPRI" = 0x002
        c_EPOLLOUT "EPOLLOUT" = 0x004
        c_EPOLLRDNORM "EPOLLRDNORM" = 0x040
        c_EPOLLRDBAND "EPOLLRDBAND" = 0x080
        c_EPOLLWRNORM "EPOLLWRNORM" = 0x100
        c_EPOLLWRBAND "EPOLLWRBAND" = 0x200
        c_EPOLLMSG "EPOLLMSG" = 0x400
        c_EPOLLERR "EPOLLERR" = 0x008
        c_EPOLLHUP "EPOLLHUP" = 0x010
        c_EPOLLET "EPOLLET" = (1 << 31)

    ctypedef union epoll_data_t:
        void *ptr
        int fd
        uint32_t u32
        uint64_t u64

    cdef struct epoll_event:
        uint32_t events
        epoll_data_t data

    int epoll_create(int size)
    int epoll_ctl(int epfd, int op, int fd, epoll_event *event)
    int epoll_wait(int epfd, epoll_event *events, int maxevents, int timeout)

cdef extern from "Python.h":
    ctypedef struct PyThreadState
    cdef extern PyThreadState *PyEval_SaveThread()
    cdef extern void PyEval_RestoreThread(PyThreadState*)

cdef call_epoll_wait(int fd, unsigned int maxevents, int timeout_msec):
    """
    Wait for an I/O event, wrap epoll_wait(2).

    @type fd: C{int}
    @param fd: The epoll file descriptor number.

    @type maxevents: C{int}
    @param maxevents: Maximum number of events returned.

    @type timeout_msec: C{int}
    @param timeout_msec: Maximum time in milliseconds waiting for events. 0
        makes it return immediately whereas -1 makes it wait indefinitely.

    @raise IOError: Raised if the underlying epoll_wait() call fails.
    """
    cdef epoll_event *events
    cdef int result
    cdef int nbytes
    cdef PyThreadState *_save

    nbytes = sizeof(epoll_event) * maxevents
    events = <epoll_event*>malloc(nbytes)
    memset(events, 0, nbytes)
    try:
        _save = PyEval_SaveThread()
        result = epoll_wait(fd, events, maxevents, timeout_msec)
        PyEval_RestoreThread(_save)

        if result == -1:
            raise IOError(errno, strerror(errno))
        results = []
        for i from 0 <= i < result:
            results.append((events[i].data.fd, <int>events[i].events))
        return results
    finally:
        free(events)

cdef class epoll:
    """
    Represent a set of file descriptors being monitored for events.
    """

    cdef int fd
    cdef int initialized

    def __init__(self, int size=1023):
        """
        The constructor arguments are compatible with select.poll.__init__.
        """
        self.fd = epoll_create(size)
        if self.fd == -1:
            raise IOError(errno, strerror(errno))
        self.initialized = 1

    def __dealloc__(self):
        if self.initialized:
            close(self.fd)
            self.initialized = 0

    def close(self):
        """
        Close the epoll file descriptor.
        """
        if self.initialized:
            if close(self.fd) == -1:
                raise IOError(errno, strerror(errno))
            self.initialized = 0

    def fileno(self):
        """
        Return the epoll file descriptor number.
        """
        return self.fd

    def register(self, int fd, int events):
        """
        Add (register) a file descriptor to be monitored by self.

        This method is compatible with select.epoll.register in Python 2.6.

        Wrap epoll_ctl(2).

        @type fd: C{int}
        @param fd: File descriptor to modify

        @type events: C{int}
        @param events: A bit set of IN, OUT, PRI, ERR, HUP, and ET.

        @raise IOError: Raised if the underlying epoll_ctl() call fails.
        """
        cdef int result
        cdef epoll_event evt
        evt.events = events
        evt.data.fd = fd
        result = epoll_ctl(self.fd, CTL_ADD, fd, &evt)
        if result == -1:
            raise IOError(errno, strerror(errno))

    def unregister(self, int fd):
        """
        Remove (unregister) a file descriptor monitored by self.

        This method is compatible with select.epoll.unregister in Python 2.6.

        Wrap epoll_ctl(2).

        @type fd: C{int}
        @param fd: File descriptor to modify

        @raise IOError: Raised if the underlying epoll_ctl() call fails.
        """
        cdef int result
        cdef epoll_event evt
        # We don't have to fill evt.events for CTL_DEL.
        evt.data.fd = fd
        result = epoll_ctl(self.fd, CTL_DEL, fd, &evt)
        if result == -1:
            raise IOError(errno, strerror(errno))

    def modify(self, int fd, int events):
        """
        Modify the modified state of a file descriptor monitored by self.

        This method is compatible with select.epoll.modify in Python 2.6.

        Wrap epoll_ctl(2).

        @type fd: C{int}
        @param fd: File descriptor to modify

        @type events: C{int}
        @param events: A bit set of IN, OUT, PRI, ERR, HUP, and ET.

        @raise IOError: Raised if the underlying epoll_ctl() call fails.
        """
        cdef int result
        cdef epoll_event evt
        evt.events = events
        evt.data.fd = fd
        result = epoll_ctl(self.fd, CTL_MOD, fd, &evt)
        if result == -1:
            raise IOError(errno, strerror(errno))

    def _control(self, int op, int fd, int events):
        """
        Modify the monitored state of a particular file descriptor.

        Wrap epoll_ctl(2).

        @type op: C{int}
        @param op: One of CTL_ADD, CTL_DEL, or CTL_MOD

        @type fd: C{int}
        @param fd: File descriptor to modify

        @type events: C{int}
        @param events: A bit set of IN, OUT, PRI, ERR, HUP, and ET.

        @raise IOError: Raised if the underlying epoll_ctl() call fails.
        """
        cdef int result
        cdef epoll_event evt
        evt.events = events
        evt.data.fd = fd
        result = epoll_ctl(self.fd, op, fd, &evt)
        if result == -1:
            raise IOError(errno, strerror(errno))

    def wait(self, unsigned int maxevents, int timeout):
        """
        Wait for an I/O event, wrap epoll_wait(2).

        @type maxevents: C{int}
        @param maxevents: Maximum number of events returned.

        @type timeout: C{int}
        @param timeout: Maximum time in milliseconds waiting for events. 0
            makes it return immediately whereas -1 makes it wait indefinitely.

        @raise IOError: Raised if the underlying epoll_wait() call fails.
        """
        return call_epoll_wait(self.fd, maxevents, timeout)

    def poll(self, float timeout=-1, unsigned int maxevents=1024):
        """
        Wait for an I/O event, wrap epoll_wait(2).

        This method is compatible with select.epoll.poll in Python 2.6.

        @type maxevents: C{int}
        @param maxevents: Maximum number of events returned.

        @type timeout: C{int}
        @param timeout: Maximum time waiting for events. 0 makes it return
            immediately whereas -1 makes it wait indefinitely.

        @raise IOError: Raised if the underlying epoll_wait() call fails.
        """
        return call_epoll_wait(self.fd, maxevents, <int>(timeout * 1000.0))


CTL_ADD = EPOLL_CTL_ADD
CTL_DEL = EPOLL_CTL_DEL
CTL_MOD = EPOLL_CTL_MOD

IN = EPOLLIN = c_EPOLLIN
OUT = EPOLLOUT = c_EPOLLOUT
PRI = EPOLLPRI = c_EPOLLPRI
ERR = EPOLLERR = c_EPOLLERR
HUP = EPOLLHUP = c_EPOLLHUP
ET = EPOLLET = c_EPOLLET

RDNORM = EPOLLRDNORM = c_EPOLLRDNORM
RDBAND = EPOLLRDBAND = c_EPOLLRDBAND
WRNORM = EPOLLWRNORM = c_EPOLLWRNORM
WRBAND = EPOLLWRBAND = c_EPOLLWRBAND
MSG = EPOLLMSG = c_EPOLLMSG
