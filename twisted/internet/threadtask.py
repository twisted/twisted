
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
        hadNoTasks = (self.threadTasks == {})
        thread = reflect.currentThread()
        if not self.threadTasks.has_key(thread):
            self.threadTasks[thread] = []
        self.threadTasks[thread].append((function, args, kwargs))

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
        for thread, tasks in self.threadTasks.items():
            func, args, kwargs = tasks.pop(0)
            apply(func, args, kwargs)
            if len(tasks) == 0: del self.threadTasks[thread]

    synchronized = ["addTask", "runUntilCurrent"]

threadable.synchronize(Scheduler)
theScheduler = Scheduler()

def schedule(function, args=[], kwargs={}):
    global theScheduler
    theScheduler.addTask(function, args, kwargs)

# sibling import - done here to prevent circular import
import main
