# -*- test-case-name: twisted.test.test_context -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""
Dynamic pseudo-scoping for Python.

Call functions with context.call({key: value}, func); func and
functions that it calls will be able to use 'context.get(key)' to
retrieve 'value'.

This is thread-safe.
"""


defaultContextDict = {}

setDefault = defaultContextDict.__setitem__

class ContextTracker:
    def __init__(self):
        self.contexts = [defaultContextDict]

    def callWithContext(self, ctx, func, *args, **kw):
        newContext = self.contexts[-1].copy()
        newContext.update(ctx)
        self.contexts.append(newContext)
        try:
            return func(*args,**kw)
        finally:
            self.contexts.pop()

    def getContext(self, key, default=None):
        return self.contexts[-1].get(key, default)


class ThreadedContextTracker:
    def __init__(self):
        import thread
        self.threadId = thread.get_ident
        self.contextPerThread = {}

    def currentContext(self):
        tkey = self.threadId()
        if not self.contextPerThread.has_key(tkey):
            self.contextPerThread[tkey] = ContextTracker()
        return self.contextPerThread[tkey]

    def callWithContext(self, ctx, func, *args, **kw):
        return self.currentContext().callWithContext(ctx, func, *args, **kw)

    def getContext(self, key, default=None):
        return self.currentContext().getContext(key, default)

def installContextTracker(ctr):
    global theContextTracker
    global call
    global get

    theContextTracker = ctr
    call = theContextTracker.callWithContext
    get = theContextTracker.getContext

def initThreads():
    newContextTracker = ThreadedContextTracker()
    newContextTracker.contextPerThread[newContextTracker.threadId()] = theContextTracker
    installContextTracker(newContextTracker)

installContextTracker(ContextTracker())

import threadable
threadable.whenThreaded(initThreads)

