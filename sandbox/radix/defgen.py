# Copyright (C) 2004 Christopher Armstrong
# This will eventually go into Twisted

from twisted.python import log

from twisted.internet.defer import Deferred, fail

class waitForDeferred:
    """
    waitForDeferred and deferredGenerator help you write
    Deferred-using code that looks like it's blocking (but isn't
    really), with the help of generators.

    There are two important functions involved: waitForDeferred, and
    deferredGenerator.

        def thingummy():
            thing = waitForDeferred(makeSomeRequestResultingInDeferred())
            yield thing
            thing = thing.getResult()
            print thing #the result! hoorj!
        thingummy = deferredGenerator(thingummy)

    waitForDeferred returns something that you should immediately yield;
    when your generator is resumed, calling thing.getResult() will either
    give you the result of the Deferred if it was a success, or raise an
    exception if it was a failure.

    deferredGenerator takes one of these waitForDeferred-using
    generator functions and converts it into a function that returns a
    Deferred. The result of the Deferred will be the last
    value that your generator yielded (remember that 'return result' won't
    work; use 'yield result; return' in place of that).

    Note that not yielding anything from your generator will make the
    Deferred result in None. Yielding a Deferred from your generator
    is also an error condition; always yield waitForDeferred(d)
    instead.

    The Deferred returned from your deferred generator may also
    errback if your generator raised an exception.

        def thingummy():
            thing = waitForDeferred(makeSomeRequestResultingInDeferred())
            yield thing
            thing = thing.getResult()
            if thing == 'I love Twisted':
                # will become the result of the Deferred
                yield 'TWISTED IS GREAT!'
                return
            else:
                # will trigger an errback
                raise Exception('DESTROY ALL LIFE')
        thingummy = deferredGenerator(thingummy)

    Put succinctly, these functions connect deferred-using code with this
    'fake blocking' style in both directions: waitForDeferred converts from
    a Deferred to the 'blocking' style, and deferredGenerator converts from
    the 'blocking' style to a Deferred.
    """
    def __init__(self, d):
        if not isinstance(d, Deferred):
            raise TypeError("You must give waitForDeferred a Deferred. You gave it %r." % (d,))
        self.d = d

    def getResult(self):
        if hasattr(self, 'failure'):
            self.failure.raiseException()
        return self.result

def _deferGenerator(g, deferred=None, result=None):
    """
    See L{waitForDeferred}.
    """
    if deferred is None:
        deferred = Deferred()
    try:
        result = g.next()
    except StopIteration:
        deferred.callback(result)
        return deferred
    except:
        deferred.errback()
        return deferred

    # Deferred.callback(Deferred) raises an error; we catch this case
    # early here and give a nicer error message to the user in case
    # they yield a Deferred. Perhaps eventually these semantics may
    # change.
    if isinstance(result, Deferred):
        return fail(TypeError("Yield waitForDeferred(d), not d!"))

    if isinstance(result, waitForDeferred):
        def gotResult(r):
            result.result = r
            _deferGenerator(g, deferred, r)
        def gotError(f):
            result.failure = f
            _deferGenerator(g, deferred, f)
        result.d.addCallbacks(gotResult, gotError)
    else:
        _deferGenerator(g, deferred, result)
    return deferred

def deferredGenerator(f):
    return lambda *args, **kwargs: _deferGenerator(f(*args, **kwargs))

