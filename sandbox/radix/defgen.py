# Copyright (C) 2004 Christopher Armstrong
# This will eventually go into Twisted

from twisted.python import log

from twisted.internet.defer import Deferred

class waitForDeferred:
    """
    waitForDeferred and deferredGenerator help you write
    Deferred-using code that looks like it's blocking (but isn't really),
    with the help of generators.

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
    Deferred. The result of the Deferred will be the last 'regular'
    value that your generator yielded, i.e., one that's not the result
    of waitForDeferred (remember that 'return result' won't work; use
    'yield result; return' in place of that). The Deferred may also
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

    Put concisely, waitForDeferred and deferredGenerator connect
    deferred-using code with this 'fake blocking' style in both
    directions: waitForDeferred converts from a Deferred to the 'blocking'
    style, and deferredGenerator converts from the 'blocking' style to a
    Deferred.
    """
    def __init__(self, d):
        assert isinstance(d, Deferred), "You must give waitForDeferred a Deferred. You gave me %r." % (d,)
        self.d = d

    def getResult(self):
        if hasattr(self, 'failure'):
            raise self.failure
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
    if isinstance(result, waitForDeferred):
        def gotResult(r):
            result.result = r
            _deferGenerator(g, deferred, r)
        def gotError(f):
            result.failure = f
            _deferGenerator(g, deferred, f)
        result.d.addCallbacks(gotResult, gotError)
        # This shouldn't ever really happen
        result.d.addErrback(log.err)
    else:
        _deferGenerator(g, deferred, result)
    return deferred

def deferredGenerator(f):
    return lambda *args, **kwargs: _deferGenerator(f(*args, **kwargs))

try:
    from bytecodehacks import macro
except ImportError:
    wait = None
    print "Warning: bytecodehacks not found, not defining wait()"
else:
    def wait((d)):
        yield d
        d = d.getResult()
    macro.add_macro(wait)

if __name__ == '__main__':
    from twisted.internet import reactor
    def testIt():

        def getThing():
            d = Deferred()
            reactor.callLater(0.5, d.callback, "hi")
            return d

        x = waitForDeferred(getThing())
        yield x
        x = x.getResult()

        assert x == "hi"
        
        if wait is not None:
            x = wait(getThing())
            assert x == "hi", "%s != 'hi'" % (x,)

        def getOwie():
            d = Deferred()
            def CRAP():
                d.errback(Exception('OMG'))
            reactor.callLater(0.5, CRAP)
            return d

        ow = waitForDeferred(getOwie())
        yield ow
        try:
            ow.getResult()
        except Exception, e:
            assert e.args == ('OMG',), repr(e.args)
        1/0 # seeing this is good
        return
    if wait is not None:
        testIt = macro.expand(testIt)

    d = _deferGenerator(testIt())
    def _(r):
        assert r == "there"
        print "wee"
    d.addCallback(_)
    d.addErrback(log.err)
    d.addBoth(lambda x: reactor.stop())
    from twisted.internet import reactor
    reactor.run()
