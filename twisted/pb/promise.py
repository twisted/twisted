# -*- test-case-name: twisted.pb.test.test_promise -*-

from twisted.python import util, failure
from twisted.internet import defer

id = util.unsignedID

EVENTUAL, FULFILLED, BROKEN = range(3)

class Promise:
    """I am a promise of a future result. I am a lot like a Deferred, except
    that my promised result is usually an instance. I make it possible to
    schedule method invocations on this future instance, returning Promises
    for the results.

    Promises are always in one of three states: Eventual, Fulfilled, and
    Broken. (see http://www.erights.org/elib/concurrency/refmech.html for a
    pretty picture). They start as Eventual, meaning we do not yet know
    whether they will resolve or not. In this state, method invocations are
    queued. Eventually the Promise will be 'resolved' into either the
    Fulfilled or the Broken state. Fulfilled means that the promise contains
    a live object to which methods can be dispatched synchronously. Broken
    promises are incapable of invoking methods: they all result in Failure.

    Method invocation is always asynchronous: it always returns a Promise.
    """

    # all our internal methods are private, to avoid colliding with normal
    # method names that users may invoke on our eventual target.

    _state = EVENTUAL
    _resolution = None

    def __init__(self, d):
        self._watchers = []
        self._pendingMethods = []
        d.addCallbacks(self._ready, self._broken)

    def _wait_for_resolution(self):
        if self._state == EVENTUAL:
            d = defer.Deferred()
            self._watchers.append(d)
        else:
            d = defer.succeed(self._resolution)
        return d

    def _ready(self, resolution):
        self._resolution = resolution
        self._state = FULFILLED
        self._run_methods()

    def _broken(self, f):
        self._resolution = f
        self._state = BROKEN
        self._run_methods()

    def _invoke_method(self, name, args, kwargs):
        if isinstance(self._resolution, failure.Failure):
            return self._resolution
        method = getattr(self._resolution, name)
        res = method(*args, **kwargs)
        return res
        
    def _run_methods(self):
        for (name, args, kwargs, result_deferred) in self._pendingMethods:
            d = defer.maybeDeferred(self._invoke_method, name, args, kwargs)
            d.addBoth(result_deferred.callback)
        del self._pendingMethods
        for d in self._watchers:
            d.callback(self._resolution)
        del self._watchers

    def __repr__(self):
        return "<Promise %#x>" % id(self)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError
        def newmethod(*args, **kwargs):
            return self._add_method(name, args, kwargs)
        return newmethod

    def _add_method(self, name, args, kwargs):
        if self._state == EVENTUAL:
            d = defer.Deferred()
            self._pendingMethods.append((name, args, kwargs, d))
        else:
            d = defer.maybeDeferred(self._invoke_method, name, args, kwargs)
        return Promise(d)


def when(p):
    """Turn a Promise into a Deferred that will fire with the enclosed object
    when it is ready. Use this when you actually need to schedule something
    to happen in a synchronous fashion. Most of the time, you can just invoke
    methods on the Promise as if it were immediately available."""
    
    assert isinstance(p, Promise)
    return p._wait_for_resolution()
