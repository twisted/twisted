#
# event.pyx
#
# libevent Python bindings
#
# Copyright (c) 2004 Dug Song <dugsong@monkey.org>
# Copyright (c) 2003 Martin Murray <murrayma@citi.umich.edu>
#
# $Id: event.pyx,v 1.3 2004/09/24 13:19:36 dugsong Exp $

"""event library

This module provides a mechanism to execute a function when a
specific event on a file handle, file descriptor, or signal occurs,
or after a given time has passed.
"""

__author__ = ( 'Dug Song <dugsong@monkey.org>',
               'Martin Murray <mmurray@monkey.org>' )
__copyright__ = ( 'Copyright (c) 2004 Dug Song',
                  'Copyright (c) 2003 Martin Murray' )
__license__ = 'BSD'
__url__ = 'http://monkey.org/~dugsong/pyevent/'
__version__ = '0.2'

import sys

cdef extern from "Python.h":
    void  Py_INCREF(object o)
    void  Py_DECREF(object o)
    
cdef extern from "event.h":
    struct timeval:
        unsigned int tv_sec
        unsigned int tv_usec
    
    struct event_t "event":
        int   ev_fd
        int   ev_flags
        void *ev_arg

    void event_init()
    void event_set(event_t *ev, int fd, short event,
                   void(*)(int, short, void *), void *arg)
    void evtimer_set(event_t *ev, void (*)(int, short, void *), void *arg)
    int  event_add(event_t *ev, timeval *tv)
    int  event_del(event_t *ev)
    int  event_dispatch()
    int  event_loop(int loop)
    int  event_pending(event_t *ev, short, timeval *tv)

    int EVLOOP_ONCE
    int EVLOOP_NONBLOCK

    int EV_TIMEOUT
    int EV_READ
    int EV_WRITE
    int EV_SIGNAL
    int EV_PERSIST
    
TIMEOUT = EV_TIMEOUT
READ    = EV_READ
WRITE   = EV_WRITE
SIGNAL  = EV_SIGNAL
PERSIST = EV_PERSIST

__event_exc = None

cdef int __event_inited

cdef int __event_sigcb():
    return -1

cdef void __event_handler(int fd, short evtype, void *arg):
    (<object>arg).__callback(evtype)

cdef class Event:
    """Event(callback, args=None, evtype=0, handle=None) -> event object
    Read(handle, callback, *args) -> event object
    Write(handle, callback, *args) -> event object
    IO(handle, callback, *args) -> event object
    Signal(sig, callback, *args) -> event object
    Timer(callback, *args) -> event object
    
    Create a new event object with a user callback.

    Arguments:

    callback -- user callback with (*args) prototype, which can return a
                non-None value to be persistent
                XXX - EV_SIGNAL events are always persistent
    args     -- optional callback arguments
    evtype   -- bitmask of EV_READ or EV_WRITE, or EV_SIGNAL
    handle   -- for EV_READ or EV_WRITE, a file handle or descriptor
                for EV_SIGNAL, a signal number
    """
    cdef event_t ev
    cdef object handle, evtype, callback, args
    cdef double timeout

    def __init__(self, callback, args=None, short evtype=0, handle=-1):
        self.callback = callback
        self.args = args
        self.evtype = evtype
        self.handle = handle
        if evtype == 0 and not handle:
            evtimer_set(&self.ev, __event_handler, <void *>self)
        elif evtype == EV_SIGNAL:
            evtype = evtype | EV_PERSIST
            event_set(&self.ev, handle, evtype, __event_handler, <void *>self)
        else:
            if type(handle) != int:
                handle = handle.fileno()
            event_set(&self.ev, handle, evtype, __event_handler, <void *>self)

    def __callback(self, short evtype):
        cdef extern int event_gotsig
        cdef extern int (*event_sigcb)()
        cdef timeval tv
        global __event_exc
        try:
            self.evtype = evtype
            if self.callback(*self.args):
                if self.timeout:
                    tv.tv_sec = <long>self.timeout
                    tv.tv_usec = (self.timeout - <double>self.timeout) * \
                                 1000000.0
                    event_add(&self.ev, &tv)
                else:
                    event_add(&self.ev, NULL)
        except:
            __event_exc = sys.exc_info()
            event_sigcb = __event_sigcb
            event_gotsig = 1
        if not event_pending(&self.ev, EV_READ|EV_WRITE|EV_SIGNAL|EV_TIMEOUT, NULL):
            Py_DECREF(self)
    
    def add(self, double timeout=0.0):
        """Add event to be executed after an optional timeout.

        Arguments:
        
        timeout -- seconds after which the event will be executed
        """
        cdef timeval tv

        if not event_pending(&self.ev, EV_READ|EV_WRITE|EV_SIGNAL|EV_TIMEOUT, NULL):
            Py_INCREF(self)
        self.timeout = timeout
        if timeout > 0.0:
            tv.tv_sec = <long>timeout
            tv.tv_usec = (timeout - <double>timeout) * 1000000.0
            event_add(&self.ev, &tv)
        else:
            event_add(&self.ev, NULL)

    def pending(self):
        """Return 1 if the event is scheduled to run, or else 0."""
        return event_pending(&self.ev, EV_TIMEOUT|EV_SIGNAL|EV_READ|EV_WRITE, NULL)
    
    def delete(self):
        """Remove event from the event queue."""
        if self.pending():
            event_del(&self.ev)
            Py_DECREF(self)
    
    def __dealloc__(self):
        self.delete()
    
    def __repr__(self):
        return '<event flags=0x%x, handle=%s, callback=%s, args=%s>' % \
               (self.ev.ev_flags, self.handle, self.callback, self.args)

class Read(Event):
    def __init__(self, handle, callback, *args):
        Event.__init__(self, callback, args, EV_READ, handle)

class Write(Event):
    def __init__(self, handle, callback, *args):
        Event.__init__(self, callback, args, EV_WRITE, handle)

class IO(Event):
    def __init__(self, handle, callback, *args):
        Event.__init__(self, callback, args, EV_READ|EV_WRITE, handle)

class Signal(Event):
    def __init__(self, sig, callback, *args):
        Event.__init__(self, callback, args, EV_SIGNAL, sig)

class Timer(Event):
    def __init__(self, callback, *args):
        Event.__init__(self, callback, args)

def init():
    """Initialize event queue."""
    if not __event_inited:
        event_init()
        __event_inited = 1

def add(Event ev, double timeout=0.0):
    """Add the specified event to the event queue, with an optional timeout."""
    ev.add(timeout)

def delete(Event ev):
    """Delete the specified event."""
    ev.delete()

def dispatch():
    """Dispatch all events on the event queue."""
    global __event_exc
    event_dispatch()
    if __event_exc:
        raise __event_exc[0], __event_exc[1], __event_exc[2]

def loop(nonblock=False):
    """Dispatch all pending events on queue in a single pass."""
    cdef int flags
    flags = EVLOOP_ONCE
    if nonblock:
        flags = EVLOOP_ONCE|EVLOOP_NONBLOCK
    event_loop(flags)

if not __event_inited:
    # XXX - make sure event queue is always initialized.
    event_init()
