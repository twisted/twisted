# -*- test-case-name: twisted.test.test_issues -*-


from twisted.issues.issue import PendingTaskCompletion
from twisted.issues import common

import time

URGENT = 5
IMPORTANT = 4
NORMAL = 3
MINOR = 2
TRIVIAL = 1

class Task(common.Commentable):
    def __init__(self, submitter, description):
        
        """A non-trivial commitment of some resource, usually developer time.
        Tasks have estimates, completion %'s, categories, dependent issues,
        dependent tasks, and may have a developer (or team) assigned to it.

        @param submitter The IssuePerson who submitted this task.

        @param description A description of the work to be done.
        """
        common.Commentable.__init__(self, submitter, description)
        self.percentage = 0
        self.priorities = []
        self.categories = []
        self.dependentIssues = []
        self.dependentTasks = []
        self.fixers = []
        self.setPriority(NORMAL)

    def assignTo(self, fixer):
        """Assign this task to a new fixer.
        """
        self.fixers.append((fixer, time.time()))

    def getCurrentFixer(self):
        return self.fixers[-1][0]

    def addDependentIssue(self, issue):
        """Add a new issue whose resolution depends on the completion of this task.
        """
        if isinstance(issue.getState(), PendingTaskCompletion):
            self.dependentIssues.append((issue, time.time()))
        else:
            assert "You can't do that."

    def addDependentTask(self, task):
        """Add a new task that depends on this one.
        """
        self.dependentTasks.append((task, time.time()))

    def setPriority(self, priority):
        self.priorities.append((priority, time.time()))

    def addCategory(self, category):
        self.categories.append(category)

    def removeCategory(self, category):
        self.categories.remove(category)

