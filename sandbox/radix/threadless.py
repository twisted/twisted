import stackless
from twisted.internet import defer

def deferredTasklet(func):
    """
    I'm a function decorator that makes a stacklessy-function (one
    that might 'block', etc) into one that returns a Deferred for
    integrating with Twisted.
    """
    def replacement(*args, **kwargs):
        d = defer.Deferred()
        def tasklet(*args, **kwargs):
            try:
                d.callback(func(*args, **kwargs))
            except:
                d.errback()
            print "hey, I just callbacked or errbacked."
        print "task...", func.__name__
        crap = stackless.tasklet(tasklet)(*args, **kwargs)
        crap.run()
        print "...let", func.__name__, crap
        return d
    return replacement


def blockOn(d):
    """
    Use me in stacklessy-code to wait for a Deferred to fire.
    XXX: If the result is an failure, raise its exception.
    """
    ch = stackless.channel()
    def cb(r):
        print "blockOnCB", r
        ch.send(r)
    d.addBoth(cb)
    return ch.receive()


def TEST():
    """
    Show off deferredTasklet and blockOn.
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
        print "got", r, "from blocking"
        return r

    getDeferred = deferredTasklet(getDeferred)


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
