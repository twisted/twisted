# -*- test-case-name: twisted.xish.test.test_xishutil -*-
#
# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.

def _isStr(s):
    """ Internal method to determine if an object is a string """
    return isinstance(s, type('')) or isinstance(s, type(u''))

class _MethodWrapper(object):
    """ Internal class for tracking method calls """
    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):
        nargs = self.args + args
        nkwargs = self.kwargs.copy()
        nkwargs.update(kwargs)
        self.method(*nargs, **nkwargs)        

class CallbackList:
    def __init__(self):
        self.callbacks = {}

    def addCallback(self, onetime, method, *args, **kwargs):
        if not method in self.callbacks:
            self.callbacks[method] = (_MethodWrapper(method, *args, **kwargs), onetime)

    def removeCallback(self, method):
        if method in self.callbacks:
            del self.callbacks[method]

    def callback(self, *args, **kwargs):
        for key, (methodwrapper, onetime) in self.callbacks.items():
            methodwrapper(*args, **kwargs)
            if onetime:
                del self.callbacks[key]

from twisted.xish import xpath

class EventDispatcher:
    def __init__(self, eventprefix = "//event/"):
        self.prefix = eventprefix
        self._eventObservers = {}
        self._xpathObservers = {}
        self._orderedXpathObserverKeys = []
        self._dispatchDepth = 0  # Flag indicating levels of dispatching in progress
        self._updateQueue = [] # Queued updates for observer ops

    def _isEvent(self, event):
        return _isStr(event) and self.prefix == event[0:len(self.prefix)]

    def addOnetimeObserver(self, event, observerfn, priority = None, *args, **kwargs):
        self._addObserver(True, event, observerfn, priority, *args, **kwargs)

    def addObserver(self, event, observerfn, priority = None, *args, **kwargs):
        self._addObserver(False, event, observerfn, priority, *args, **kwargs)

    # AddObserver takes several different types of arguments
    # - xpath (string or object form)
    # - event designator (string that starts with a known prefix)
    def _addObserver(self, onetime, event, observerfn, priority, *args, **kwargs):
        # If this is happening in the middle of the dispatch, queue
        # it up for processing after the dispatch completes
        if self._dispatchDepth > 0:
            self._updateQueue.append(lambda:self.addObserver(event, observerfn, priority, *args, **kwargs))
            return

        observers = None

        if _isStr(event):
            if self.prefix == event[0:len(self.prefix)]:
                # Treat as event
                observers = self._eventObservers
            else:
                # Treat as xpath
                event = xpath.internQuery(event)
                if (priority != None):
                    event.priority = priority
                else:
                    event.priority = 0
                observers = self._xpathObservers
        else:
            # Treat as xpath
            observers = self._xpathObservers

        if not event in observers:
            cbl = CallbackList()
            cbl.addCallback(onetime, observerfn, *args, **kwargs)
            observers[event] = cbl
        else:
            observers[event].addCallback(onetime, observerfn, *args, **kwargs)

        # Update the priority ordered list of xpath keys --
        # This really oughta be rethought for efficiency
        self._orderedXpathObserverKeys = self._xpathObservers.keys()
        self._orderedXpathObserverKeys.sort()
        self._orderedXpathObserverKeys.reverse()


    def removeObserver(self, event, observerfn):
        # If this is happening in the middle of the dispatch, queue
        # it up for processing after the dispatch completes
        if self._dispatchDepth > 0:
            self._updateQueue.append(lambda:self.removeObserver(event, observerfn))
            return

        observers = None

        if _isStr(event):
            if self.prefix == event[0:len(self.prefix)]:
                observers = self._eventObservers
            else:
                event = xpath.internQuery(event)
                observers = self._xpathObservers
        else:
            observers = self._xpathObservers

        assert event in observers
        observers[event].removeCallback(observerfn)

        # Update the priority ordered list of xpath keys --
        # This really oughta be rethought for efficiency
        self._orderedXpathObserverKeys = self._xpathObservers.keys()
        self._orderedXpathObserverKeys.sort()
        self._orderedXpathObserverKeys.reverse()


    def dispatch(self, object, event = None):
        foundTarget = False
        
        # Aiyiyi! If this dispatch occurs within a dispatch
        # we need to preserve the original dispatching flag
        # and not mess up the updateQueue
        self._dispatchDepth = self._dispatchDepth + 1
            
        if event != None:
            if event in self._eventObservers:
                self._eventObservers[event].callback(object)
                foundTarget = True
        else:
            for query in self._orderedXpathObserverKeys:
                callbacklist = self._xpathObservers[query]
                if query.matches(object):
                    callbacklist.callback(object)
                    foundTarget = True

        self._dispatchDepth = self._dispatchDepth -1

        # If this is a dispatch within a dispatch, don't
        # do anything with the updateQueue -- it needs to
        # wait until we've back all the way out of the stack
        if self._dispatchDepth == 0:
            # Deal with pending update operations
            for f in self._updateQueue:
                f()
            self._updateQueue = []

        return foundTarget
