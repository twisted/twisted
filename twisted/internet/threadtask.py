
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

"""Allow threads to schedule tasks to be run by the main event loop.

This lets threads execute non-thread safe code by adding it to the
scheduler. This module should not be used by non-threaded modules,
instead they should use twisted.internet.task.

Tasks added to this scheduler will *not* be stored persistently.

This is an implementation of the Active Object pattern, and can be used
as part of the queueing layer for the Async/Half-Async pattern. For more
details:

  1) POSA2 book - http://www.cs.wustl.edu/~schmidt/POSA/    
  
  2) Active Object - http://www.cs.wustl.edu/~schmidt/PDF/Act-Obj.pdf
  
  3) Async/Half-Async - http://www.cs.wustl.edu/~schmidt/PDF/PLoP-95.pdf

Note: the API for DeferredResults is not final - I'm open to suggestions
on how to improve it.  --itamar
"""

# twisted import
from twisted.python import threadable, reflect


class Scheduler:
    """I am a thread-aware delayed scheduler of for synchronous event loops.

    Each thread has a set of tasks, which have interleaved execution phases.
    """
    def __init__(self):
        self.threadTasks = {}

    def __getstate__(self):
        dict = copy.copy(self.__dict__)
        dict['threadTasks'] = {}
        return dict

    def addTask(self, function, args=[], kwargs={}):
        """Schedule a function to be called by the main event-loop thread.
        
        The result of the function will not be returned.
        """
        threadTasks = self.threadTasks
        hadNoTasks = (threadTasks == {})
        thread = reflect.currentThread()
        
        if not threadTasks.has_key(thread):
            threadTasks[thread] = []
        threadTasks[thread].append((function, args, kwargs))
        if hadNoTasks:
            main.wakeUp()

    def addTaskWithResult(self, function, args=[], kwargs={}):
        """Schedule a function, returning a DeferredResult object.
        
        The result of the function can be gotten by calling the get()
        method of this DeferredResult object.
        """
        args = [function,] + list(args)
        dresult = DeferredResult()
        self.addTask(dresult._doAction, args, kwargs)
        return dresult
    
    def timeout(self):
        """Either I have work to do immediately, or no work to do at all.
        """
        if self.threadTasks:
            return 0.
        else:
            return None

    def runUntilCurrent(self):
        threadTasks = self.threadTasks
        for thread, tasks in threadTasks.items():
            func, args, kwargs = tasks.pop(0)
            apply(func, args, kwargs)
            if len(tasks) == 0: del threadTasks[thread]

    synchronized = ["addTask", "runUntilCurrent"]

threadable.synchronize(Scheduler)


class NotReady(RuntimeError):
    """The DeferredResult does not yet have a result."""


class DeferredResult:
    """Result of a scheduled operation that is deferred.
    
    We can get the result of the operation by calling the get() method, which
    will raise a NotReady exception if the result is not available. Otherwise it
    returns the result of the operation, or if it raised an exception, reraise
    that exception.
    
    The exception catching will only work for class-based exceptions, but
    hopefully by now string exceptions are rare.
    """
    
    def __init__(self):
        self._finished = 0
    
    def haveResult(self):
        """Did we get the result yet?"""
        return self._finished
    
    def get(self):
        """Return the result or if it's not available raise NotReady"""
        if not self._finished:
            raise NotReady, "we don't have the result yet."
        
        if hasattr(self, '_exception'):
            raise self._exception
        else:
            return self._result
    
    def _doAction(self, function, *args, **kwargs):
        """Run the action whose result we are. 
        
        Should only be called by the scheduler."""
        try:
            result = apply(function, args, kwargs)
        except Exception, e:
            self._exception = exception
        else:
            self._result = result
        self._finished = 1


theScheduler = Scheduler()

def schedule(function, args=[], kwargs={}):
    """Schedule a function to be called by the main event loop thread"""
    global theScheduler
    theScheduler.addTask(function, args, kwargs)

def scheduleWithResult(function, args=[], kwargs={}):
    """Schedule a function to be called by the main event loop thread.
    
    Returns a DeferredResult object, allowing us to get the result of the
    function.
    
    XXX this name sucks. Someone think of a new one please.
    """
    global theScheduler
    return theScheduler.addTaskWithResult(function, args, kwargs)


# sibling import - done here to prevent circular import
import main
