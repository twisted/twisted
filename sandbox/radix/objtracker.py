import gc, sys, weakref

class ObjTracker:
    """
    A debugging aid that shows you how an object is travelling through
    code.
    """


    def install(self):
        """
        Start tracking objects.

        WARNING: NO objects will be collected between a call to
        L{install} and L{reset}.
        """
        self.reset()
        sys.settrace(self.globalTrace)


    def reset(self):
        """
        Clean everything out. This gives a chance to Python to clean
        up all of its objects.
        """
        self.refs = []
        self.objsToFuncs = {}


    def remove(self):
        """
        Remove the tracer. Note that this will remove whatever trace
        function you have installed, whether it is the objtracker or
        not.
        """
        sys.settrace(None)


    def getObjectFlow(self, o):
        """
        Get the flow the given object took through code.
        """
        return self.objsToFuncs[id(o)]


    def globalTrace(self, frame, event, arg):
        return self.localTrace


    def localTrace(self, frame, event, arg):
        referents = self.getReferents(frame)
        for o in referents:
            self.refs.append(o) # keep a reference around
            l = self.objsToFuncs.setdefault(id(o), [])
            fname = frame.f_code.co_name
            l.append((event, fname, frame.f_lineno))
        return self.localTrace


    def getReferents(self, obj, cache=None):
        """
        Return a list of all objects that an object references, no
        matter how far away it is; this is cycle-safe.
        """
        if cache is None:
            cache = {}
        if (id(obj) in cache):
            return
        for referent in gc.get_referents(obj):
            cache[id(referent)] = referent
            self.getReferents(referent, cache)
        return cache.values()


if __name__ == '__main__':
    class Foo:
        pass
    o = Foo()
    
    def foo(x):
        bar(x)
        return baz(x)

    def bar(y):
        hash(y)
        return y == 2

    def baz(z):
        while 1:
            if z is z:
                break
        return z

    ot = ObjTracker()
    ot.install()
    foo(o)
    ot.remove()
    import pprint
    pprint.pprint(ot.getObjectFlow(o))
    ## prints:

##[('line', 'foo', 75),
## ('line', 'bar', 79),
## ('line', 'bar', 80),
## ('return', 'bar', 80),
## ('line', 'foo', 76),
## ('line', 'baz', 83),
## ('line', 'baz', 84),
## ('line', 'baz', 85),
## ('line', 'baz', 86),
## ('return', 'baz', 86),
## ('return', 'foo', 76)]
