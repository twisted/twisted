# -*- test-case-name: twisted.test.test_context -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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

