# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
See how fast deferreds are.

This is mainly useful to compare cdefer.Deferred to defer.Deferred
"""


from twisted.internet import defer
from timer import timeit

benchmarkFuncs = []

def benchmarkFunc(iter, args=()):
    """
    A decorator for benchmark functions that measure a single iteration
    count. Registers the function with the given iteration count to the global
    benchmarkFuncs list
    """
    def decorator(func):
        benchmarkFuncs.append((func, args, iter))
        return func
    return decorator

def benchmarkNFunc(iter, ns):
    """
    A decorator for benchmark functions that measure multiple iteration
    counts. Registers the function with the given iteration count to the global
    benchmarkFuncs list.
    """
    def decorator(func):
        for n in ns:
            benchmarkFuncs.append((func, (n,), iter))
        return func
    return decorator

def instantiate():
    """
    Only create a deferred
    """
    d = defer.Deferred()
instantiate = benchmarkFunc(100000)(instantiate)

def instantiateShootCallback():
    """
    Create a deferred and give it a normal result
    """
    d = defer.Deferred()
    d.callback(1)
instantiateShootCallback = benchmarkFunc(100000)(instantiateShootCallback)

def instantiateShootErrback():
    """
    Create a deferred and give it an exception result. To avoid Unhandled
    Errors, also register an errback that eats the error
    """
    d = defer.Deferred()
    try:
        1/0
    except:
        d.errback()
    d.addErrback(lambda x: None)
instantiateShootErrback = benchmarkFunc(200)(instantiateShootErrback)

ns = [10, 1000, 10000]

def instantiateAddCallbacksNoResult(n):
    """
    Creates a deferred and adds a trivial callback/errback/both to it the given
    number of times.
    """
    d = defer.Deferred()
    def f(result):
        return result
    for i in xrange(n):
        d.addCallback(f)
        d.addErrback(f)
        d.addBoth(f)
        d.addCallbacks(f, f)
instantiateAddCallbacksNoResult = benchmarkNFunc(20, ns)(instantiateAddCallbacksNoResult)

def instantiateAddCallbacksBeforeResult(n):
    """
    Create a deferred and adds a trivial callback/errback/both to it the given
    number of times, and then shoots a result through all of the callbacks.
    """
    d = defer.Deferred()
    def f(result):
        return result
    for i in xrange(n):
        d.addCallback(f)
        d.addErrback(f)
        d.addBoth(f)
        d.addCallbacks(f)
    d.callback(1)
instantiateAddCallbacksBeforeResult = benchmarkNFunc(20, ns)(instantiateAddCallbacksBeforeResult)

def instantiateAddCallbacksAfterResult(n):
    """
    Create a deferred, shoots it and then adds a trivial callback/errback/both
    to it the given number of times. The result is processed through the
    callbacks as they are added.
    """
    d = defer.Deferred()
    def f(result):
        return result
    d.callback(1)
    for i in xrange(n):
        d.addCallback(f)
        d.addErrback(f)
        d.addBoth(f)
        d.addCallbacks(f)
instantiateAddCallbacksAfterResult = benchmarkNFunc(20, ns)(instantiateAddCallbacksAfterResult)

def pauseUnpause(n):
    """
    Adds the given number of callbacks/errbacks/both to a deferred while it is
    paused, and unpauses it, trigerring the processing of the value through the
    callbacks.
    """
    d = defer.Deferred()
    def f(result):
        return result
    d.callback(1)
    d.pause()
    for i in xrange(n):
        d.addCallback(f)
        d.addErrback(f)
        d.addBoth(f)
        d.addCallbacks(f)
    d.unpause()
pauseUnpause = benchmarkNFunc(20, ns)(pauseUnpause)

def benchmark():
    """
    Run all of the benchmarks registered in the benchmarkFuncs list
    """
    print defer.Deferred.__module__
    for func, args, iter in benchmarkFuncs:
        print func.__name__, args, timeit(func, iter, *args)

if __name__ == '__main__':
    benchmark()
