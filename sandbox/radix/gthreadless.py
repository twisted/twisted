import greenlet
from twisted.internet import defer

def _desc(g):
    if isinstance(g, DebugGreenlet):
        if hasattr(g, 'name'):
            desc = "<%s %s" % (g.name, hex(id(g)))
        else:
            desc = "<NO NAME!? %s" % (hex(id(g)), )
    else:
        desc = "<%s" % (hex(id(g)),)
    if g is greenlet.main:
        desc += " (main)"
    desc += ">"
    return desc


class DebugGreenlet(greenlet.greenlet):
    __slots__ = ('name',)
    def __init__(self, func, name=None):
        super(DebugGreenlet, self).__init__(func)
        self.name = name
    def switch(self, *args, **kwargs):
        current = greenlet.getcurrent()
        #print "%s -> %s" % (_desc(current), _desc(self))
        return super(DebugGreenlet, self).switch(*args, **kwargs)

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
        #crap = DebugGreenlet(greenfunc, func.__name__)
        g = greenlet.greenlet(greenfunc)
        #print _desc(greenlet.getcurrent()), "->", _desc(g)
        crap = g.switch(*args, **kwargs)
        #print "Back from Crap", _desc(greenlet.getcurrent()), "<-", _desc(g), crap
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

    #print _desc(g.parent), mainOrNot, "<-", hex(id(g)), "(%s)" % (desc,)

    ## Note ##
    # Notice that this code catches and ignores SystemExit. The
    # greenlet mechanism sends a SystemExit at a blocking greenlet if
    # there is no chance that the greenlet will be fired by anyone
    # else -- that is, no other greenlets have a reference to the one
    # that's blocking.

    # This is often the case with blockOn. When someone blocks on a
    # Deferred, these callbacks are added to it. When the deferred
    # fires, we make the blockOn() call finish -- we resume the
    # blocker.  At that point, the Deferred chain is irrelevant; it
    # makes no sense for any other callbacks to be called. The
    # Deferred, then, will likely be garbage collected and thus all
    # references to our greenlet will be lost -- and thus it will have
    # SystemExit fired.

    def cb(r):
        #print _desc(greenlet.getcurrent()), "~~>", _desc(g), "(%s)" % (desc,), r
        try:
            g.switch(r)
        except SystemExit:
            pass
            #print "GREENLETS ARE BUGGERED at", _desc(greenlet.getcurrent())
        #print "After a callback", _desc(greenlet.getcurrent())
    def eb(f):
        #print _desc(greenlet.getcurrent()), "~~>", _desc(g), "(%s)" % (desc,), f
        try:
            #print "Sending an", f, "to", g
            #import pdb; pdb.set_trace()
            g.switch(_IAmAnException(f))
        except SystemExit:
            pass
            #print "GREENLETS ARE BUGGERED at", _desc(greenlet.getcurrent())
        #print "After an errback", _desc(greenlet.getcurrent())
    #print "Adding callbacks", _desc(greenlet.getcurrent())
    d.addCallbacks(cb, eb)
    #d.addErrback(eb)

    #x = greenlet.main.switch()
    #print "Switching to parent", _desc(greenlet.getcurrent())
    x = g.parent.switch()
    #print "Back from parent", _desc(greenlet.getcurrent())
    #print "back from parent! got", repr(x)
    if isinstance(x, _IAmAnException):
        #print "Raising exception", _desc(greenlet.getcurrent())
        x.f.raiseException()
    #print "Returning x", x, _desc(greenlet.getcurrent())
##    import pdb
##    if x == 'goofledorf': pdb.set_trace()
    return x


"""
#BUG

defer(block(defer(block(defer))))
defer. defer. <- defer. <-defer.

g0 N-> g1 (main defers to g1)
g1 N-> g2 (g1 defers to g2)
g2 B-> g1 (g2 blocks; goes back to parent)
g1 B-> g0 (g1 blocks; goes back to parent)
g0 C-> g2 (g0 calls cb for g2's deferred)
g2 C-> g1 (g2 calls cb for g1's deferred)
g1 S-> g0 ???

"""

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

