
import Queue

from twisted.internet import reactor
from twisted.internet import defer
from twisted.python import failure

class ThreadWrapper(object):
    def __init__(self, wrappee):
        self.wrappee = wrappee
    
    def __getattribute__(self, name):
        wrappee = super(ThreadWrapper, self).__getattribute__('wrappee')
        original = getattr(wrappee, name)
        if callable(original):
            return CallableWrapper(original)
        return original

class CallableWrapper(object):
    def __init__(self, original):
        self.original = original
        self.queue = Queue.Queue()
    
    def __call__(__self, *__a, **__kw):
        reactor.callFromThread(__self.__callFromThread, __a, __kw)
        result = __self.queue.get()
        if isinstance(result, failure.Failure):
            result.raiseException()
        return result
    
    def __callFromThread(self, a, kw):
        result = defer.maybeDeferred(self.original, *a, **kw)
        result.addBoth(self.queue.put)

class Asynchronous(object):
    def syncResult(self, v):
        return v

    def asyncResult(self, n, v):
        d = defer.Deferred()
        reactor.callLater(n, d.callback, v)
        return d
    
    def syncException(self):
        1/0
    
    def asyncException(self, n):
        def fail():
            try:
                1/0
            except:
                d.errback()
        d = defer.Deferred()
        reactor.callLater(n, fail)
        return d

def threadedFunction():
    tr = ThreadWrapper(reactor)
    sync = ThreadWrapper(Asynchronous())
    
    assert sync.syncResult("foo") == "foo"
    assert sync.asyncResult(0.5, "bar") == "bar"
    
    try:
        sync.syncException()
    except ZeroDivisionError:
        pass
    else:
        assert False, "ZeroDivisionError not raised"
    
    try:
        sync.asyncException(0.5)
    except ZeroDivisionError:
        pass
    else:
        assert False, "ZeroDivisionError not raised"

    print '4 tests passed'
    tr.stop()

def test():
    reactor.callInThread(threadedFunction)
    reactor.run()

test()
    