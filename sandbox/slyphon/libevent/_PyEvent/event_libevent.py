from types import *
import libevent

EV_TIMEOUT = 0x01
EV_READ = 0x02
EV_WRITE = 0x04
EV_SIGNAL = 0x08
EV_PERSIST = 0x10

EVLOOP_ONCE = 0x01
EVLOOP_NONBLOCK = 0x02

dispatch = libevent.dispatch # only returns on error

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

class EventAlreadyInittedError(Exception):
    pass

class EventNotInittedError(Exception):
    pass

class EventManager(object):
    _init_called = False
    _signals = {}

    def event_init(cls):
        if cls._init_called:
            raise EventAlreadyInittedError, 'you already initted the event loop!'
        libevent.event_init()
    event_init = classmethod(event_init)

    def signal(cls, signal, callback, argument=None):
        if get_signal(signal):
            cls.remove_signal(signal)
            cls.signal(signal, callback, argument)
        else:
            cls._signals[signal] = Event(signal, SIGNAL|PERSIST, callback, argument)
    signal = classmethod(signal)

    def get_signal(cls, signal):
        if cls._signals.has_key(signal):
            return cls._signals[signal]
        else:
            return None
    get_signal = classmethod(get_signal)

    def remove_signal(cls, signal):
        if cls.get_signal(signal) != None: 
            return
        else:
            print cls.get_signal(signal)
            cls._signals[signal].abort()
            del cls._signals[signal]
            cls._signals[signal] = None
    remove_signal = classmethod(remove_signal)

    def event_loop(cls, flags):
        if not _init_called:
            raise EventLoopNotInittedError, "you must init the event API before calling event_loop"
        libevent.event_loop(flags)
    event_loop = classmethod(event_loop)

signal = EventManager.signal
get_signal = EventManager.get_signal
remove_signal = EventManager.remove_signal
event_init = EventManager.event_init
event_loop = EventManager.event_loop


