cdef extern from "Python.h":
    void Py_INCREF(object)
    void Py_DECREF(object)
    object PyErr_Occurred()
    
cdef extern from "unistd.h":
    struct timeval:
        long tv_sec
        long tv_usec

cdef extern from "stdio.h":
    void perror(char *s)
    int printf(char *format, ...)

cdef extern from "event.h":
    struct event:
        int event_fd
    void _c_event_init "event_init"()
    int event_dispatch()
    int _c_event_loop "event_loop" (int flags)
    void event_set(event *ev, int fd, short event, void (*fn)(int, short, void *) except *, void *arg)
    int event_add(event *ev, timeval *tv)
    int event_del(event *ev)
    int event_pending(event *ev, short event, timeval *tv)
    int event_initialized(event *ev)
    void evtimer_set(event *ev, void (*fn)(int, short, void *) except *, void *arg)
    void evtimer_add(event *ev, timeval *tv)
    void evtimer_del(event *ev)
    int evtimer_pending(event *ev, timeval *tv)
    int evtimer_initialized(event *ev)
    void signal_set(event *ev, int signal, void (*fn)(int, short, void *) except *, void *arg)
    void signal_add(event *ev, timeval *tv)
    void signal_del(event *ev)
    int signal_pending(event *ev, timeval *tv)
    int signal_initialized(event *ev)
    int (*event_sigcb)()
    int event_gotsig
    extern int errno

cdef extern from "eventpy.h":
    event *allocate_event()
    void free_event(event *ev)
    timeval *allocate_timeval()
    void free_timeval(timeval *tv)

cdef void bounceback(int fd, short eve, void *args) except *:
    # Declaring thismay be very inefficient
    # http://www.cosc.canterbury.ac.nz/~greg/python/Pyrex/version/Doc/overview.html
    # under the heading 'ERROR RETURN VALUES'
    (<object>args).callback(fd, eve)
        
EV_TIMEOUT = 0x01
EV_READ = 0x02
EV_WRITE = 0x04
EV_SIGNAL = 0x08
EV_PERSIST = 0x10
EVLOOP_ONCE = 0x01
EVLOOP_NONBLOCK = 0x02

_init_called = False

def event_init():
    _c_event_init()

def event_loop(flags=EVLOOP_ONCE|EVLOOP_NONBLOCK):
    _c_event_loop(flags)

cdef class _Event:
    cdef event *ev
    cdef timeval *tv
    def __new__(self, *args):
        # pyrex docs suggest adding *args to all __new__ declarations to ease
        # subclassing. see:
        # http://www.cosc.canterbury.ac.nz/~greg/python/Pyrex/version/Doc/special_methods.html
        self.ev = allocate_event()
        self.tv = allocate_timeval()
        self.tv.tv_sec = 0
        self.tv.tv_usec = 0

    def set_timeout(self, seconds, microseconds):
        if seconds < 0 or microseconds < 0:
            raise "_Event.set_timeout() seconds and microseconds may not be negative."
        self.tv.tv_sec = seconds
        self.tv.tv_usec = microseconds
 
    def go(self):
        Py_INCREF(self)
        if self.tv.tv_sec == 0 and self.tv.tv_usec == 0:
            event_add(self.ev, NULL)
        else:
            event_add(self.ev, self.tv)

    def __init__(self, int fd, short event, seconds, microseconds, *args):
        # Remember, __init__ may be called more than once, or not called at all
        if fd is None:
            raise "_Event.__init__() fd must not be None."
        if event is None:
            raise "_Event.__init__() event must not be None."
        event_set(self.ev, fd, event, bounceback, <void *>self)
        if event & EV_PERSIST:
            self.persistent = 1
        else:
            self.persistent = 0
        self.seconds, self.microseconds = (seconds, microseconds)
        self.set_timeout(seconds, microseconds)
#        self.go()

    def abort(self):
        if event_pending(self.ev, EV_TIMEOUT|EV_READ|EV_WRITE, NULL):
            event_del(self.ev)
            Py_DECREF(self)

    def __del__(self):
        if self is not None:
            self.abort()

    def __dealloc__(self):
        free_event(self.ev)
        free_timeval(self.tv)
    
    def callback(self, fd, eve):
        self.pycallback(fd, eve, self.pyargument)
        Py_DECREF(self)
        if not self.persistent:
            Py_DECREF(self)
        else:
            if eve & EV_TIMEOUT:
                self.set_timeout(self.seconds, self.microseconds)
            self.go()

def dispatch():
    # XXX: Errno handling?
    ret=event_dispatch()
    if ret < 0:
        perror("event.dispatch")
        return -errno
    return ret

def loop(flags):
    ret = event_loop(flags)
    if ret < 0:
        perror("event.loop")
        return -errno
    return ret
