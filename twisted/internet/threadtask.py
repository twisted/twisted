"""Allow threads to schedule tasks to be run by the main event loop.

This lets threads execute non-thread safe code by adding it to the
scheduler. This module should not be used by non-threaded modules,
instead they should use twisted.internet.task.
"""

# twisted import
from twisted.python import threadable, reflect


class Scheduler:
    """I am a thread-aware delayed scheduler of for synchronous event loops.

    Each thread has a set of tasks, which have interleaved execution phases.
    """
    def __init__(self):
        self.threadTasks = {}

    def addTask(self, function, args=[], kwargs={}):
        hadNoTasks = (self.threadTasks == {})
        thread = reflect.currentThread()
        if not self.threadTasks.has_key(thread):
            self.threadTasks[thread] = []
        self.threadTasks[thread].append((function, args, kwargs))
        
        if hadNoTasks:
            # import here to prevent circular import
            import main
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
    theScheduler.addTask(function, args, kwargs)
