
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

"""A task scheduler that is integrated with the main event loop.
"""

# System Imports

import traceback

# Twisted Imports

from twisted.python import threadable, log


class ThreadedScheduler:
    """I am a thread-aware delayed scheduler of for synchronous event loops.

    This lets threads execute non-thread safe code by adding it to the
    scheduler. Tasks added to this scheduler will *not* be stored persistently.

    This is an implementation of the Active Object pattern, and can be used
    as part of the queueing layer for the Async/Half-Async pattern. The other
    half the Async/Half-Async pattern is twisted.internet.threadtask.
    
    For more details:

      1) POSA2 book - http://www.cs.wustl.edu/~schmidt/POSA/    

      2) Active Object - http://www.cs.wustl.edu/~schmidt/PDF/Act-Obj.pdf

      3) Async/Half-Async - http://www.cs.wustl.edu/~schmidt/PDF/PLoP-95.pdf
    """
    def __init__(self):
        self.threadTasks = {}
        self._lock = thread.allocate_lock()

    def __getstate__(self):
        return None
    
    def __setstate__(self):
        self.__init__()
    
    def addTask(self, function, *args, **kwargs):
        """Schedule a function to be called by the main event-loop thread.
        
        The result of the function will not be returned.
        """
        threadTasks = self.threadTasks
        hadNoTasks = (threadTasks == {})
        id = thread.get_ident()
        
        self._lock.acquire()
        try:
            if not threadTasks.has_key(id):
                threadTasks[id] = [(function, args, kwargs)]
            else:
                threadTasks[id].append((function, args, kwargs))
        finally:
            self._lock.release()
        
        if hadNoTasks:
            main.wakeUp()
    
    def timeout(self):
        """Either I have work to do immediately, or no work to do at all.
        """
        if self.threadTasks:
            return 0.
        else:
            return None

    def runUntilCurrent(self):
        threadTasks = self.threadTasks
        tasksTodo = []
        
        self._lock.acquire()
        try:
            for thread, tasks in threadTasks.items():
                tasksTodo.append(tasks.pop(0))
                if tasks: tasksTodo.append(tasks.pop(0))
                if not tasks:
                    del threadTasks[thread]
        finally:
            self._lock.release()
        
        for func, args, kwargs in tasksTodo:
            apply(func, args, kwargs)


class Scheduler:
    """I am a non-thread-safe delayed scheduler for synchronous event loops.
    """
    
    def __init__(self):
        self.tasks = []

    def addTask(self, function, *args, **kwargs):
        self.tasks.append((function, args, kwargs))

    def timeout(self):
        """Either I have work to do immediately, or no work to do at all.
        """
        if self.tasks:
            return 0.
        else:
            return None
    
    def runUntilCurrent(self):
        tasks = self.tasks
        self.tasks = []
        for function, args, kwargs in tasks:
            apply(function, args, kwargs)


def initThreads():
    global theScheduler, thread, schedule
    import thread
    
    # Sibling Imports
    import main
    
    # there may already be a registered scheduler, so we need to get
    # rid of it.
    try:
        main.removeDelayed(theScheduler)
    except NameError:
        pass
    
    theScheduler = ThreadedScheduler()
    schedule = theScheduler.addTask
    main.addDelayed(theScheduler)


threadable.whenThreaded(initThreads)
theScheduler = Scheduler()

schedule = theScheduler.addTask

def doAllTasks():
    """Run all tasks in the scheduler.
    """
    while theScheduler.timeout() != None:
        theScheduler.runUntilCurrent()


class Task:
    """I am a set of steps that get executed.

    Each "step" is a method to call and some arguments to call it with.  I am
    to be used with the Scheduler class - after each step is called I will
    readd myself to the scheduler if I still have steps to do.
    """
    
    def __init__(self, steps=None, scheduler=theScheduler):
        """Create a Task.
        """
        # Format for 'steps' is [[func,args,kw],[func,args,kw], ...]
        if steps:
            self.steps = steps
        else:
            self.steps = []
        self.progress = 0
        self.scheduler = scheduler

    def addWork(self, callable, *args, **kw):
        self.steps.append([callable, args, kw])

    def __call__(self):
        if self.progress < len(self.steps):
            func, args, kw = self.steps[self.progress]
            try:
                apply(func, args, kw)
            except:
                log.msg( 'Exception in Task' )
                traceback.print_exc(file=log.logfile)
                return 0
            else:
                self.progress = self.progress + 1
                # if we still have tasks left we add ourselves to the scheduler
                if self.progress < len(self.steps):
                    self.scheduler.addTask(self)
                return 1
        return 0


# Sibling Imports
import main
main.addDelayed(theScheduler)
