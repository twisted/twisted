# -*- test-case-name: twisted.words.test.test_xishutil -*-
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

from twisted.words.xish import xpath, domish

class EventDispatcher:
    """ Event dispatching service.

    The C{EventDispatcher} allows observers to be registered for certain events
    that are dispatched. There are two types of events: XPath events and Named
    events.
    
    Every dispatch is triggered by calling L{dispatch} with a data object and,
    for named events, the name of the event.
    
    When an XPath type event is dispatched, the associated object is assumed
    to be a L{domish.Element} object, which is matched against all registered
    XPath queries. For every match, the respective observer will be called with
    the data object.

    A named event will simply call each registered observer for that particular
    event name, with the data object. Unlike XPath type events, the data object
    is not restricted to L{domish.Element}, but can be anything.

    When registering observers, the event that is to be observed is specified
    using an L{xpath.XPathQuery} object or a string. In the latter case, the
    string can also contain the string representation of an XPath expression.
    To distinguish these from named events, each named event should start with
    a special prefix that is stored in C{self.prefix}. It defaults to
    C{//event/}.

    Observers registered using L{addObserver} are persistent: after the
    observer has been triggered by a dispatch, it remains registered for a
    possible next dispatch. If instead L{addOnetimeObserver} was used to
    observe an event, the observer is removed from the list of observers after
    the first observed event.

    Obsevers can also prioritized, by providing an optional C{priority}
    parameter to the L{addObserver} and L{addOnetimeObserver} methods. Higher
    priority observers are then called before lower priority observers.

    Finally, observers can be unregistered by using L{removeObserver}.
    
    """
 
    def __init__(self, eventprefix = "//event/"):
        self.prefix = eventprefix
        self._eventObservers = {}
        self._xpathObservers = {}
        self._orderedEventObserverKeys = []
        self._orderedXpathObserverKeys = []
        self._dispatchDepth = 0  # Flag indicating levels of dispatching in progress
        self._updateQueue = [] # Queued updates for observer ops

    def _isEvent(self, event):
        return _isStr(event) and self.prefix == event[0:len(self.prefix)]

    def addOnetimeObserver(self, event, observerfn, priority=0, *args, **kwargs):
        """ Register a one-time observer for an event.

        Like L{addObserver}, but is only triggered at most once. See there
        for a description of the parameters.
        """
        self._addObserver(True, event, observerfn, priority, *args, **kwargs)

    def addObserver(self, event, observerfn, priority=0, *args, **kwargs):
        """ Register an observer for an event.

        Each observer will be registered with a certain priority. Higher
        priority observers get called before lower priority observers.

        @param event: Name or XPath query for the event to be monitored.
        @type event: L{str} or L{xpath.XPathQuery}.
        @param observerfn: Function to be called when the specified event
                           has been triggered. This function takes
                           one parameter: the data object that triggered
                           the event. When specified, the C{*args} and
                           C{**kwargs} parameters to addObserver are being used
                           as additional parameters to the registered observer
                           function.
        @param priority: (Optional) priority of this observer in relation to
                         other observer that match the same event. Defaults to
                         C{0}.
        @type priority: L{int}
        """
        self._addObserver(False, event, observerfn, priority, *args, **kwargs)

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
                observers = self._xpathObservers
        else:
            # Treat as xpath
            observers = self._xpathObservers

        key = (priority, event)
        if not key in observers:
            cbl = CallbackList()
            cbl.addCallback(onetime, observerfn, *args, **kwargs)
            observers[key] = cbl
        else:
            observers[key].addCallback(onetime, observerfn, *args, **kwargs)

        # Update the priority ordered list of xpath keys --
        # This really oughta be rethought for efficiency
        self._orderedEventObserverKeys = self._eventObservers.keys()
        self._orderedEventObserverKeys.sort()
        self._orderedEventObserverKeys.reverse()
        self._orderedXpathObserverKeys = self._xpathObservers.keys()
        self._orderedXpathObserverKeys.sort()
        self._orderedXpathObserverKeys.reverse()

    def removeObserver(self, event, observerfn):
        """ Remove function as observer for an event.

        The observer function is removed for all priority levels for the
        specified event.
        
        @param event: Event for which the observer function was registered.
        @type event: L{str} or L{xpath.XPathQuery}
        @param observerfn: Observer function to be unregistered.
        """

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

        for priority, query in observers:
            if event == query:
                observers[(priority, query)].removeCallback(observerfn)

        # Update the priority ordered list of xpath keys --
        # This really oughta be rethought for efficiency
        self._orderedEventObserverKeys = self._eventObservers.keys()
        self._orderedEventObserverKeys.sort()
        self._orderedEventObserverKeys.reverse()
        self._orderedXpathObserverKeys = self._xpathObservers.keys()
        self._orderedXpathObserverKeys.sort()
        self._orderedXpathObserverKeys.reverse()

    def dispatch(self, object, event = None):
        """ Dispatch an event.
        
        When C{event} is C{None}, an XPath type event is triggered, and
        C{object} is assumed to be an instance of {domish.Element}. Otherwise,
        C{event} holds the name of the named event being triggered. In the
        latter case, C{object} can be anything.

        @param object: The object to be dispatched.
        @param event: Optional event name.
        @type event: L{str}
        """

        foundTarget = False
        
        # Aiyiyi! If this dispatch occurs within a dispatch
        # we need to preserve the original dispatching flag
        # and not mess up the updateQueue
        self._dispatchDepth = self._dispatchDepth + 1
            
        if event != None:
            for priority, query in self._orderedEventObserverKeys:
                if event == query:
                    self._eventObservers[(priority, event)].callback(object)
                    foundTarget = True
        else:
            for priority, query in self._orderedXpathObserverKeys:
                callbacklist = self._xpathObservers[(priority, query)]
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
