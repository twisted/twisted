
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


# System Imports

import traceback

# Twisted Imports

from twisted.python import threadable, log

class Task:
    """I am a set of steps that get executed.

    Each "step" is a method to call and some arguments to call it with.  I am
    to be used with the Scheduler class.
    """
    
    def __init__(self, steps=None):
        """Create a Task.
        """
        # Format for 'steps' is [[func,args,kw],[func,args,kw], ...]
        self.steps = []
        self.progress = 0

    def addWork(self, callable, *args, **kw):
        self.steps.append([callable, args, kw])

    def next(self):
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
                return 1
        return 0



class Scheduler:
    """I am a delayed scheduler for synchronous event loops.

    I am really a set of tasks, which have interleaved execution phases.  Each
    time runUntilCurrent is called, I call each task's next() method; if the
    task has more work to do, I'll keep it around.
    """
    def __init__(self):
        self.tasks = []

    def addTask(self, task):
        self.tasks.append(task)

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
        for task in tasks:
            moreWork = task.next()
            if moreWork:
                self.tasks.append(task)


theScheduler = Scheduler()

def schedule(task):
    theScheduler.addTask(task)

def wakeAndSchedule(task):
    theScheduler.addTask(task)
    main.wakeUp()

if threadable.threaded:
    schedule = wakeAndSchedule


def doAllTasks():
    while theScheduler.tasks:
        theScheduler.runUntilCurrent()

# Sibling Imports

import main
