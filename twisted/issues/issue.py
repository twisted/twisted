# -*- test-case-name: twisted.test.test_issues -*-

import time

import common

class IssueQueue:
    """A queue of issues to be responded to (at least roughly) in order.
    """
    def __init__(self, name):
        self.name = name
        self.issues = []
        self.fixers = []

    def addListeningFixer(self, fixer):
        self.fixers.append(fixer)

    def addIssue(self, issue):
        """Add an incoming issue to the queue. Notify anyone interested in this event.
        """
        for fixer in self.fixers:
            fixer.notifyText("New Issue Available On Queue %s" % self.name)
        self.issues.append(issue)

    def removeIssue(self, issue):
        """Remove a specific issue from the queue.
        """
        self.issues.remove(issue)

    def respondToNextIssue(self, fixer):
        """Respond to the next issue in the queue.
        """
        self.issues[0].setState(InConversation(fixer))
    
class Issue(common.Commentable):
    """A thing that can be worked on; the base component of pretty much
    everything.  An issue is a state machine.  It has one state at a time; that
    state, however, is an instance of its own, and it may have information
    associated with it.
    """

    def __init__(self, issueFinder, description, initialState, number):
        common.Commentable.__init__(self, issueFinder, description)
        self.states = []
        self.setState(initialState)
        self.number = number

    def getFinder(self):
        return self.comments[0][0]

    def setState(self, newState):
        if self.states:
            oldState = self.states[-1]
        else:
            oldState = None
        self.states.append(newState)
        newState.enter(self)
        if oldState:
            oldState.exit()

    def getState(self):
        return self.states[-1]

    def getStatusMessage(self):
        return self.getState().getStatusMessage()

class IssueState:
    """A representation of the current state of an Issue instance.
    """

    def getStatusMessage(self):
        """A small descriptive text message that will be presented to the user.

        This will be in a sentence following the phrase 'Issue #54084 is now '.
        The default message is 'in an unknown state'.
        """
        return "in an unknown state"
    
    def entered(self):
        """Override me for special behavior when this state is entered.
        """

    def exited(self):
        """Override me for special behavior when this state is entered.
        """

    def enter(self, issue):
        self.issue = issue
        self.enterTime = time.time()
        self.entered()

    def exit(self):
        self.exitTime = time.time()
        self.exited()

class InQueue(IssueState):

    """The state of an issue as it is waiting for a real-time response, in a
    queue of similar issues."""

    def __init__(self, queue):
        """Create an InQueue state.

        @param queue The queue that the issue (is/was) in (while it is / when
        it was) in this state.
        """
        self.queue = queue

    def getStatusMessage(self):
        return "in queue: %r" % self.queue.name

    def entered(self):
        self.queue.addIssue(self.issue)

    def exited(self):
        self.queue.removeIssue(self.issue)

class InTransfer(IssueState):
    """ The state of an issue as it is waiting to be transferred between two
    different IssueFixers.
    """

    def __init__(self, fixer1, fixer2):
        self.fixer1 = fixer1
        self.fixer2 = fixer2

    def entered(self):
        self.fixer2.notifyText("THERE IS AN ISSUE WAITING FOR YOU: #%s" %
                               self.issue.number)
        # self.fixer2.inTransfer[self.issue.number] = self.issue

    def exited(self):
        self.fixer1.notifyText("ISSUE #%s HAS BEEN REDEEMED" %
                               self.issue.number)
        # del self.fixer2.inTransfer[self.issue.number]

    def getStatusMessage(self):
        return "being transferred to %s" % (self.fixer2.perspectiveName)


class InConversation(IssueState):
    """The state of an issue as it is being answered in real time.
    BeingAnswered issues are associated with an issue finder and and issue
    fixer, as well as a transcript of the conversation between them. """

    def __init__(self, fixer, finder=None):
        self.fixer = fixer
        self.finder = finder

    def entered(self):
        if not self.finder:
            self.finder = self.issue.getFinder()
        self.fixer.notifyFinderReady(self.finder, self.issue)
        self.finder.notifyFixerReady(self.fixer, self.issue)
        t = self.finder.beginTranscribing(self.fixer)
        self.transcript = t
        self.finder.currentlyFinding[self.issue.number] = self.issue
        self.fixer.currentlyFixing[self.issue.number] = self.issue

    def exited(self):
        del self.finder.currentlyFinding[self.issue.number]
        del self.fixer.currentlyFixing[self.issue.number]
        self.transcript.endTranscript()
        self.fixer.notifyFinderGone(self.finder, self.issue)
        self.finder.notifyFixerGone(self.fixer, self.issue)


class PendingTaskCompletion(IssueState):
    """The state of an issue that is not being dealt with in realtime. This is
    the state that has unfinished Tasks associated with it.  """

    def __init__(self, task):
        self.task = task

    def getStatusMessage(self):
        return "pending the resolution of a task"

    def entered(self):
        self.task.addDependentIssue(self.issue)
        # blah blah, wait for notification of task completion, abracadabra

    def exited(self):
        self.task.removeDependentIssue(self.issue)

class PendingFinderConfirmation(IssueState):
    """The state of an issue with completed tasks but no confirmation of
    resolution from the Finder.
    """

class FixerClosed(IssueState):
    """The state of an issue which has been closed by a fixer as needing no
    further attention, but has not been confirmed explicitly by the finder of
    the issue.  This is a user-interface convenience for systems where the
    finders are not paying on a per-issue basis, so open issues don't need to
    be left in the system.  """

    def getStatusMessage(self):
        return "considered fixed"

class Fixed(IssueState):
    """The state of an issue that has been resolved to the satisfaction of the
    Finder.  This is the terminal state of the Issue state machine.
    """

    def getStatusMessage(self):
        return "fixed"

