
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

"""
A module that will allow your program to be multi-threaded,
micro-threaded, and single-threaded.  Currently microthreads are
unimplemented.  The idea is to abstract away some commonly used
functionality so that I don't have to special-case it in all programs.
"""

import traceback
import sys

class ThreadableError(Exception): pass

class _Waiter:
    def __init__(self):
        self.callbacks = {}
        self.results = {}
        self.conditions = {}

    def registerCallback(self, key, callback=None, errback=None):
        self.callbacks[key] = errback, callback

    def hasCallback(self, key):
        return self.callbacks.has_key(key)

    def preWait(self, key):
        pass

    def block(self):
        pass

    def wait(self, key):
        self.conditions[key] = 1
        while not self.results.has_key(key):
            # This call will ostensibly eventually populate this
            # dictionary.
            self.block()
        r, is_ok = self.results[key]
        del self.results[key]
        if is_ok:
            return r
        else:
            raise r


    def runCallback(self, key, value, ok):
        call_or_err = self.callbacks.get(key)
        if not call_or_err:
            return 0
        callback = call_or_err[ok]
        if callback is None:
            del self.callbacks[key]
            return 1

        try:
            callback(value)
            del self.callbacks[key]
            return 1
        except:
            log.deferr()
            del self.callbacks[key]
            return 2

    def unwait(self, key, value, ok):
        if not self.runCallback(key, value, ok):
            self.results[key] = (value, ok)
            if self.conditions.has_key(key):
                del self.conditions[key]

    def unwait_all(self):
        for k in self.conditions.keys():
            self.unwait(k, ThreadableError("Shut Down."), 0)


class _ThreadedWaiter(_Waiter):
    synchronized = ['registerCallback',
                    'hasCallback',
                    'preWait',
                    'unwait']

    def __init__(self):
        _Waiter.__init__(self)

    def preWait(self, key):
        global ioThread
        if threadmodule.get_ident() == ioThread:
            return _Waiter.preWait(self, key)
        cond = self.conditions[key] = threadingmodule.Condition()
        cond.acquire()

    def wait(self, key):
        global ioThread
        if threadmodule.get_ident() == ioThread:
            return _Waiter.wait(self, key)
        cond = self.conditions[key]
        cond.wait()
        # ...
        r, is_ok = self.results[key]
        del self.conditions[key]
        del self.results[key]
        cond.release()

        if is_ok:
            return r
        else:
            raise r


    def unwait(self, key, value, ok):
        if not self.runCallback(key, value, ok):
            cond = self.conditions.get(key)
            if cond is None:
                self.results[key] = (value,ok)
            else:
                cond.acquire()
                self.results[key] = (value, ok)
                cond.notify()
                cond.release()

class _XLock:
    """
    Exclusive lock class.  The advantage of this over threading.RLock
    is that it's picklable (kinda...).  The goal is to one day not be
    dependent upon threading, and to have this work for any old
    'thread'
    """
    
    def __init__(self):
        assert threaded,\
               "Locks may not be allocated in an unthreaded environment!"

        self.block = threadmodule.allocate_lock()
        self.count = 0
        self.owner = 0

    def __setstate__(self, state):
        self.__init__()

    def __getstate__(self):
        return None

    def withThisLocked(self, func, *args, **kw):
        self.acquire()
        try:
            return apply(func,args,kw)
        finally:
            self.release()

    def acquire(self):
        current = threadmodule.get_ident()
        if self.owner == current:
            self.count = self.count + 1
            return 1
        self.block.acquire()
        self.owner = current
        self.count = 1

    def release(self):
        current = threadmodule.get_ident()
        if self.owner != current:
            raise "Release of unacquired lock."

        self.count = self.count - 1

        if self.count == 0:
            self.owner = None
            self.block.release()

##def _synch_init(self, *a, **b):
##    self.lock = XLock()

def _synchPre(self, *a, **b):
    if not self.__dict__.has_key('_threadable_lock'):
        _synchLockCreator.acquire()
        if not self.__dict__.has_key('_threadable_lock'):
            self.__dict__['_threadable_lock'] = XLock()
        _synchLockCreator.release()
    self._threadable_lock.acquire()

def _synchPost(self, *a, **b):
    self._threadable_lock.release()

_to_be_synched = []

def synchronize(*klasses):
    """Make all methods listed in each class' synchronized attribute synchronized.

    The synchronized attribute should be a list of strings, consisting of the
    names of methods that must be synchronized. If we are running in threaded
    mode these methods will be wrapped with a lock.
    """
    global _to_be_synched
    if not threaded:
        map(_to_be_synched.append, klasses)
        return

    if threaded:
        import hook
        for klass in klasses:
##            hook.addPre(klass, '__init__', _synch_init)
            for methodName in klass.synchronized:
                hook.addPre(klass, methodName, _synchPre)
                hook.addPost(klass, methodName, _synchPost)

threaded = None
ioThread = None
threadCallbacks = []

def whenThreaded(cb):
    if threaded:
        cb()
    else:
        threadCallbacks.append(cb)

def init(with_threads=1):
    """Initialize threading. Should be run once, at the beginning of program.
    """
    global threaded, _to_be_synched, Waiter
    global threadingmodule, threadmodule, XLock, _synchLockCreator
    if threaded == with_threads:
        return
    elif threaded:
        raise RuntimeError("threads cannot be disabled, once enabled")
    threaded = with_threads
    if threaded:
        log.msg('Enabling Multithreading.')
        import thread, threading
        threadmodule = thread
        threadingmodule = threading
        Waiter = _ThreadedWaiter
        XLock = _XLock
        _synchLockCreator = XLock()
        synchronize(*_to_be_synched)
        _to_be_synched = []
        for cb in threadCallbacks:
            cb()
    else:
        Waiter = _Waiter
        # Hack to allow XLocks to be unpickled on an unthreaded system.
        class DummyXLock:
            pass
        XLock = DummyXLock


def isInIOThread():
    """Are we in the thread responsable for I/O requests (the event loop)?
    """
    global threaded
    global ioThread
    if threaded:
        if (ioThread == threadmodule.get_ident()):
            return 1
        else:
            return 0
    return 1


def registerAsIOThread():
    """Mark the current thread as responsable for I/O requests.
    """
    global threaded
    global ioThread
    if threaded:
        import thread
        ioThread = thread.get_ident()


synchronize(_ThreadedWaiter)
init(0)

# sibling imports
import log
