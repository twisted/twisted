import greenlet
from twisted.internet import defer

def deferredGreenlet(func):
    """
    I am a function decorator for functions that call blockOn.  The
    function I return will call the original function inside of a
    greenlet, and return a Deferred.

    XXX: Do a hack so the name of 'replacement' is the name of 'func'.
    """
    def replacement(*args, **kwargs):
        d = defer.Deferred()
        def greenfunc(*args, **kwargs):
            try:
                d.callback(func(*args, **kwargs))
            except:
                d.errback()
        crap = greenlet.greenlet(greenfunc)
        #print hex(id(greenlet.getcurrent())), "->", hex(id(crap))
        crap = crap.switch(*args, **kwargs)
        return d
    return replacement

class CalledFromMain(Exception):
    pass

class _IAmAnException(object):
    def __init__(self, f):
        self.f = f

def blockOn(d, desc=None):
    """
    Use me in non-main greenlets to wait for a Deferred to fire.
    """
    g = greenlet.getcurrent()
    if g is greenlet.main:
        raise CalledFromMain("You cannot call blockOn from the main greenlet.")

    if g.parent is greenlet.main:
        mainOrNot =  "(main)"
    else:
        mainOrNot = ""

    #print hex(id(g.parent)), mainOrNot, "<-", hex(id(g)), "(%s)" % (desc,)

    def cb(r):
        #print hex(id(greenlet.getcurrent())), "~~>", hex(id(g)), "(%s)" % (desc,)
        g.switch(r)
    def eb(f):
        #print hex(id(greenlet.getcurrent())), "~~>", hex(id(g)), "(%s)" % (desc,)
        try:
            g.switch(_IAmAnException(f))
        except SystemExit:
            print "GREENLETS ARE BUGGERED"
    d.addCallback(cb)
    d.addErrback(eb)

    #x = greenlet.main.switch()
    x = g.parent.switch()
    #print "back from parent! got", repr(x)
    if isinstance(x, _IAmAnException):
        x.f.raiseException()
    return x

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
            def wrapper(*a, **kw):
                result = original(*a, **kw)
                if isinstance(result, defer.Deferred):
                    return blockOn(result)
                return result
            return wrapper
        return original

