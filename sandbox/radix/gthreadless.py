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


def TEST():
    """
    Show off deferredGreenlet and blockOn.
    """
    from twisted.internet import reactor

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
        reactor.stop()

    d.addCallback(_cbJunk)
    print "kicking it off!"
    reactor.run()
    

if __name__ == '__main__':
    TEST()
