# -*- test-case-name: twisted.test.test_xishutil -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

def _isStr(s):
    """Internal method to determine if an object is a string """
    return isinstance(s, type('')) or isinstance(s, type(u''))

class _MethodWrapper(object):
    """Internal class for tracking method calls """
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
        self._dispatchDepth = 0  # Flag indicating levels of dispatching in progress
        self._updateQueue = [] # Queued updates for observer ops

    def _isEvent(self, event):
        return _isStr(event) and self.prefix == event[0:len(self.prefix)]

    def addOnetimeObserver(self, event, observerfn, *args, **kwargs):
        self._addObserver(True, event, observerfn, *args, **kwargs)

    def addObserver(self, event, observerfn, *args, **kwargs):
        self._addObserver(False, event, observerfn, *args, **kwargs)

    # AddObserver takes several different types of arguments
    # - xpath (string or object form)
    # - event designator (string that starts with a known prefix)
    def _addObserver(self, onetime, event, observerfn, *args, **kwargs):
        # If this is happening in the middle of the dispatch, queue
        # it up for processing after the dispatch completes
        if self._dispatchDepth > 0:
            self._updateQueue.append(lambda:self.addObserver(event, observerfn, *args, **kwargs))
            return

        observers = None

        if _isStr(event):
            if self.prefix == event[0:len(self.prefix)]:
                # Treat as event
                observers = self._eventObservers
            else:
                # Treat as xpath
                event = xpath.intern(event)
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
                event = xpath.intern(event)
                observers = self._xpathObservers
        else:
            observers = self._xpathObservers

        assert event in observers
        observers[event].removeCallback(observerfn)


    def dispatch(self, object, event = None):
        # Aiyiyi! If this dispatch occurs within a dispatch
        # we need to preserve the original dispatching flag
        # and not mess up the updateQueue
        self._dispatchDepth = self._dispatchDepth + 1
            
        if event != None:
            if event in self._eventObservers:
                self._eventObservers[event].callback(object)
        else:
            for (query, callbacklist) in self._xpathObservers.iteritems():
                if query.matches(object):
                    callbacklist.callback(object)

        self._dispatchDepth = self._dispatchDepth -1

        # If this is a dispatch within a dispatch, don't
        # do anything with the updateQueue -- it needs to
        # wait until we've back all the way out of the stack
        if self._dispatchDepth == 0:
            # Deal with pending update operations
            for f in self._updateQueue:
                f()
            self._updateQueue = []
            
