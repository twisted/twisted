import greenlet
from twisted.internet import defer

def deferredGreenlet(func):
    """
    I'm a function decorator that makes a greenletty-function (one
    that might 'block', etc) into one that returns a Deferred for
    integrating with Twisted.

    XXX: Do a hack so the name of 'replacement' is the name of 'func'.
    """
    def replacement(*args, **kwargs):
        d = defer.Deferred()
        def greenfunc(*args, **kwargs):
            try:
                d.callback(func(*args, **kwargs))
            except:
                d.errback()
        crap = greenlet.greenlet(greenfunc).switch(*args, **kwargs)
        return d
    return replacement


def blockOn(d):
    """
    Use me in grenletty-code to wait for a Deferred to fire.
    XXX: If the result is a failure, raise its exception.
    """
    g = greenlet.getcurrent()
    def cb(r):
        print "blockOnCB", r
        g.switch(r)
    d.addBoth(cb)
    return greenlet.main.switch()

class GreenletWrapper(object):   
    """Wrap an object which presents an asynchronous interface (via Deferreds).
    
    The wrapped object will present the same interface, but all methods will
    return results, rather than Deferreds.
    
    When a Deferred would otherwise be returned, a greenlet is created and then
    control is switched back to the main greenlet.  When the Deferred fires,
    control is switched back to the created greenlet and execution resumes with
    the result.
    """

    def __init__(self, wrappee):  
        self.wrappee = wrappee

    def __getattribute__(self, name):
        wrappee = super(GreenletWrapper, self).__getattribute__('wrappee')
        original = getattr(wrappee, name)
        if callable(original):
            def outerWrapper(*a, **kw):
                assert greenlet.getcurrent() is not greenlet.main
                def innerWrapper():
                    # result = greenlet.greenlet(original).switch(*a, **kw)
                    result = original(*a, **kw)
                    if isinstance(result, defer.Deferred):   
                        return blockOn(result)
                    return result
                return greenlet.greenlet(innerWrapper).switch()
            return outerWrapper
        return original

class Asynchronous(object):
    def syncResult(self, v):
        return v

    def asyncResult(self, n, v):
        from twisted.internet import reactor
        d = defer.Deferred()
        reactor.callLater(n, d.callback, v)
        return d
    
    def syncException(self):
        1/0
    
    def asyncException(self, n):
        from twisted.internet import reactor
        def fail():
            try:
                1/0
            except:
                d.errback()
        d = defer.Deferred()
        reactor.callLater(n, fail)
        return d

def TEST():
    """
    Show off deferredGreenlet and blockOn.
    """
    from twisted.internet import reactor

    FINISHED = []

    import time
    #let's make sure we're not blocking anywhere
    def timer():
        print "time!", time.time()
        reactor.callLater(0.5, timer)
    reactor.callLater(0, timer)

    def getDeferred():
        d = defer.Deferred()
        reactor.callLater(3, d.callback, 'goofledorf')
        print "blocking on", d
        r = blockOn(d)
        print "got", r, "from blocking on", d
        return r

    getDeferred = deferredGreenlet(getDeferred)


    # below is our 'legacy' Twisted code that only knows about
    # Deferreds, not crazy stackless stuff.

    print "getDeferred is", getDeferred
    d = getDeferred()
    print "d is", d

    def _cbJunk(r):
        print "RESULT", r
        FINISHED.append(None)
        if len(FINISHED) == 2:
            reactor.stop()

    d.addCallback(_cbJunk)
    print "kicking it off!"
    
    # And here is some code that doesn't want to be bothered with stupid
    # trivialities like calling blockOn.
    def magic():
        o = GreenletWrapper(Asynchronous())
        print o.syncResult(3), o.asyncResult(0.1, 4)
        assert o.syncResult(3) == 3
        assert o.asyncResult(0.1, 4) == 4
        try:
            o.syncException()
        except ZeroDivisionError:
            pass
        else:
            assert False
        
        try:
            o.asyncException(0.1)
        except ZeroDivisionError:
            pass
        else:
            assert False
        print '4 magic tests passed'

    def f(result):
        print 'great, bye'
        FINISHED.append(None)
        if len(FINISHED) == 2:
            reactor.stop()
    deferredGreenlet(magic)().addCallback(f)
    
    reactor.run()
    

if __name__ == '__main__':
    TEST()
