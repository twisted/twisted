from types import *
import time
# following snippet from RawServer.py from BitTorrent-3.3 distribution
# see selectpoll.py for LICENSE and other information.
try:
    from select import poll, error, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1000
except ImportError:
    from selectpoll import poll, error, POLLIN, POLLOUT, POLLERR, POLLHUP
    timemult = 1
# end snippet
    
EV_TIMEOUT = 0x01
EV_READ = 0x02
EV_WRITE = 0x04
EV_SIGNAL = 0x08
EV_PERSIST = 0x10
EVLOOP_ONCE = 0x01
EVLOOP_NONBLOCK = 0x02

_events = {}
_timedevents = []
_pollobject = poll()

def _addEvent(this_event):
    if this_event.event & EV_PERSIST:
        _timedevents.append(this_event)
    if this_event.fd >= 0:
        _events[this_event.fd] = this_event
        mask = 0
        if this_event.event & EV_READ:
            mask = mask | POLLIN
        if this_event.event & EV_WRITE:
            mask = mask | POLLOUT
        _pollobject.register(this_event.fd, mask)

def _removeEvent(this_event):
    if this_event in _timedevents:
        _timedevents.remove(this_event)
    if this_event.fd >= 0:
        _pollobject.unregister(this_event.fd)
        del _events[this_event.fd]

def loop(flags):
    if len(_events.keys()) == 0 and len(_timedevents) == 0:
        return
    if not (flags & EVLOOP_NONBLOCK):
        firstEvent = _timedevents[0]
        minimum_tv = firstEvent.timeout
        for i in _timedevents:
            if i.current_time < minimum_tv:
                minimum_tv = i.current_time
        start_time = time.time()
        fds = _pollobject.poll(minimum_tv*1000.0)
    else:
        start_time = time.time()
        fds = _pollobject.poll(0.0)
    execution_time = time.time() - start_time
    callbacks = []
    for iter in fds:
        fd, event = iter
        event_object = _events[fd]
        mask = 0
        if event & POLLIN:
            mask = mask | EV_READ
        if event & POLLOUT:
            mask = mask | EV_WRITE
        callbacks.append( (event_object.callback, fd, mask))
    for event in _timedevents:
        if event.event & EV_TIMEOUT:
            event.current_time -= execution_time
            if event.current_time <= 0.0:
                callbacks.append((event.callback, event.fd, EV_TIMEOUT))
    for callback in callbacks:
        fun, fd, event = callback
        fun(fd, event)

def dispatch():
    while 1:
        loop(0)
        
class Event:
    def __init__(self, file, event, callback, argument=None, timeout=0.0):
        if type(file) is FileType or hasattr(file, "fileno"):
            self.fd = file.fileno()
        elif type(file) is IntType:
            self.fd = file
        else:
            raise TypeError, "file argument must be a file object or an integer!"
        if callback == None:
            raise TypeError, "callback may not be None"
        self.pycallback = callback
        self.pyargument = argument
        self.seconds = int(timeout)
        self.microseconds = int(timeout*1000) - self.seconds*1000
        self.timeout = timeout
        self.event = event
        self.registered = 0
        if event & EV_PERSIST:
            self.persistent = 1
        else:
            self.persistent = 0
        self.set_timeout(self.seconds, self.microseconds)

    def set_timeout(self, seconds, microseconds):
        if self.registered:
            raise "Event.set_timeout(): event already pending."
        if seconds < 0 or microseconds < 0:
            raise "Event.ste_timeout(): seconds and microseconds must not be negative."
        self.seconds = int(seconds)
        self.microseconds = int(microseconds)
        self.timeout = seconds + (microseconds/1000.0)

    def go(self):
        if self.registered:
            raise "Event.go() Event already pending."
        _addEvent(self)
        self.registered = 1
        self.current_time = self.timeout

    def abort(self):
        if self.registered:
            _removeEvent(self)

    def callback(self, fd, eve):
        if not self.persistent:
            _removeEvent(self)
        else:
            self.current_time = self.timeout
        self.pycallback(fd, eve, self.pyargument)

class Timer(Event):
    pass

_signals = {}
def signal(signal, callback, argument=None):
    if get_signal(signal):
        remove_signal(signal)
        signal(signal, callback, argument)
    else:
        _signals[signal] = Event(signal, SIGNAL|PERSIST, callback, argument)

def get_signal(signal):
    if _signals.has_key(signal):
        return _signals[signal]
    else:
        return None

def remove_signal(signal):
    if get_signal(signal) != None: 
        return
    else:
        print get_signal(signal)
        _signals[signal].abort()
        del _signals[signal]
        _signals[signal] = None



