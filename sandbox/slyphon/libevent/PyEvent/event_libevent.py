from types import *
import libevent

EV_TIMEOUT = 0x01
EV_READ = 0x02
EV_WRITE = 0x04
EV_SIGNAL = 0x08
EV_PERSIST = 0x10

EVLOOP_ONCE = 0x01
EVLOOP_NONBLOCK = 0x02

loop = libevent.loop
dispatch = libevent.dispatch

class Event(libevent._Event):
    def __init__(self, file, event, callback, argument=None, timeout=0.0):
        if type(file) is FileType or hasattr(file, "fileno"):
            self.fd = file.fileno()
        elif type(file) is IntType:
            self.fd = file
        else:
            raise TypeError("file argument must be a file object or an integer!")
        if callback == None:
            raise TypeError("callback may not be None")
        self.pycallback = callback
        self.pyargument = argument
        self.seconds = int(timeout)
        self.event = event
        self.registered = 0
        self.microseconds = int(timeout*1000000) - self.seconds*1000000
        libevent._Event.__init__(self, self.fd, event, self.seconds, self.microseconds)

class Timer(Event):
    def __init__(self, callback, argument=None, timeout=0.0):
        Event.__init__(0, TIMEOUT, callback, argument, timeout)

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



