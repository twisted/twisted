
"""
Helper class to writing deterministic time-based unit tests.

Do not use this module.  It is a lie.  See L{twisted.test.test_task.Clock}
instead, but don't use that either because it might also be a lie.
"""

class Clock(object):
    rightNow = 0.0

    def __call__(self):
        return self.rightNow

    def install(self):
        # Violation is fun.
        from twisted.internet import base, task
        from twisted.python import runtime
        self.base_original = base.seconds
        self.task_original = task.seconds
        self.runtime_original = runtime.seconds
        base.seconds = self
        task.seconds = self
        runtime.seconds = self

    def uninstall(self):
        from twisted.internet import base, task
        from twisted.python import runtime
        base.seconds = self.base_original
        runtime.seconds = self.runtime_original
        task.seconds = self.task_original
    
    def adjust(self, amount):
        self.rightNow += amount

    def pump(self, reactor, timings):
        timings = list(timings)
        timings.reverse()
        self.adjust(timings.pop())
        while timings:
            self.adjust(timings.pop())
            reactor.iterate()
            reactor.iterate()

