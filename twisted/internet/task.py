
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

def doAllTasks():
    while theScheduler.tasks:
        theScheduler.runUntilCurrent()
