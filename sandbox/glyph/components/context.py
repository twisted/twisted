
"""
Dynamic pseudo-scoping for Python.

Call functions with context.call({key: value}, func); func and functions that
it calls will be able to use 'context.get(key)' to retrieve 'value'.

This is thread-safe.
"""

from interface import Interface
from facets import Faceted, Facet

defaultContext = Faceted()

class ContextTracker(object):
    __slots__ = ['contexts']
    def __init__(self):
        self.contexts = [defaultContext]

    def callWithContext(self, ctx, func, *args, **kw):
        newContext = self.contexts[-1].copy()
        newContext.update(ctx)
        return self.callWithNew(newContext, func, *args, **kw)

    def callWithNew(self, ctx, func, *args, **kw):
        self.contexts.append(ctx)
        try:
            return func(*args,**kw)
        finally:
            self.contexts.pop()

    def currentContext(self):
        return self.contexts[-1]

class ThreadedContextTracker(object):
    __slots__ = ['threadId', 'contextPerThread']

    def __init__(self):
        import thread
        self.threadId = thread.get_ident
        self.contextPerThread = {}

    def currentTracker(self):
        tkey = self.threadId()
        if not self.contextPerThread.has_key(tkey):
            self.contextPerThread[tkey] = ContextTracker()
        return self.contextPerThread[tkey]

    def currentContext(self):
        return self.currentTracker().currentContext()

    def callWithContext(self, ctx, func, *args, **kw):
        return self.currentTracker().callWithContext(ctx, func, *args, **kw)

class Capture:
    """I can capture a context.  Mostly useful for managing deferred callbacks,
    like this::

        def doIt(self):
            return self.doDefer().addCallback(context.Capture(self.keepDoingIt))

    But also providing support for capturing through interfaces, like this::

        def connectIt(self):
            return reactor.connectTCP('localhost',8080, context.Capture(
                MyClientFactory(),
                interfacesToCapture = [IProtocol]))

    In the first case, the callback keepDoingIt will be run in the same context
    that the method doIt was called in.  In the latter, all methods on the
    MyClientFactory instance will be called in the context that the connectIt
    method was called in, and all methods and properties which implement the
    IProtocol interface returned from the MyClientFactory instance will too.
    """

    def __init__(self, original, interfacesToCapture=[], context=None):
        """Create a context capturer around a method or instance.
        """
        self.__original = original
        if context == None:
            context = current()
        self.__context = context
        self.__interfacesToCapture = interfacesToCapture

    def __copy(self, value):
        """Make a copy of this capturer with a new value.
        """
        return Capture(value, self.__interfacesToCapture, self.__context)

    def __provided(self, value):
        for iface in self.__interfacesToCapture:
            if iface.providedBy(value):
                return True
        return False

    def __call__(self, *args,**kw):
        value = new(self.__context, self.__original, *args, **kw)
        if self.__provided(value):
            return self.__copy(value)
        return value

    def __getattr__(self, name):
        orig = getattr(self.__original, name)
        if callable(orig) or self.__provided(orig):
            return self.__copy(orig)
        else:
            return orig

def __conform__(iface):
    cnfrm = current().__conform__(iface)
    return cnfrm

def installContextTracker(ctr):
    global theContextTracker
    global call
    global new
    global current

    theContextTracker = ctr
    call = theContextTracker.callWithContext
    new = theContextTracker.callWithNew
    current = theContextTracker.currentContext

def initThreads():
    newContextTracker = ThreadedContextTracker()
    newContextTracker.contextPerThread[newContextTracker.threadId()] = theContextTracker
    installContextTracker(newContextTracker)

installContextTracker(ContextTracker())

from twisted.python import threadable
threadable.whenThreaded(initThreads)

def test():
    import context
    
    class IA(Interface):
        pass
    class IB(Interface):
        pass

    from twisted.internet.defer import Deferred
    def a(result):
        print result, IA(context), IB(context)

    def b():
        print IA(context), IB(context)
        return Deferred().addCallback(context.Capture(a))

    context.call({IA: 1, IB: 2}, b).callback(IA(context,3))

if __name__ == '__main__':
    test()
