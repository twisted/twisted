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

try:
    from threading import local
except ImportError:
    local = None

from twisted.python import threadable

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


class _ThreadedContextTracker:
    def __init__(self):
        self.threadId = threadable.getThreadID
        self.contextPerThread = {}

    def currentContext(self):
        tkey = self.threadId()
        try:
            return self.contextPerThread[tkey]
        except KeyError:
            ct = self.contextPerThread[tkey] = ContextTracker()
            return ct

    def callWithContext(self, ctx, func, *args, **kw):
        return self.currentContext().callWithContext(ctx, func, *args, **kw)

    def getContext(self, key, default=None):
        return self.currentContext().getContext(key, default)


class _TLSContextTracker(_ThreadedContextTracker):
    def __init__(self):
        self.storage = local()

    def currentContext(self):
        try:
            return self.storage.ct
        except AttributeError:
            ct = self.storage.ct = ContextTracker()
            return ct

if local is None:
    ThreadedContextTracker = _ThreadedContextTracker
else:
    ThreadedContextTracker = _TLSContextTracker

def installContextTracker(ctr):
    global theContextTracker
    global call
    global get

    theContextTracker = ctr
    call = theContextTracker.callWithContext
    get = theContextTracker.getContext

installContextTracker(ThreadedContextTracker())
