# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
# 

from pyunit import unittest

from twisted.issues import issue, task, repo

queueName = "Lifecycle Test"

class DummyTranscript:
    def endTranscript(self):
        """end the transcript
        """

class DummyNotifier:
    def notifyFixerReady(self, fixer, issue):
        pass
    def notifyFinderReady(self, finder, issue):
        pass
    def notifyText(self, text):
        pass
    def beginTranscribing(self, other):
        return DummyTranscript()
    def notifyFinderGone(self, issueFinder, issue):
        pass
    def notifyFixerGone(self, issueFixer, issue):
        pass
class TestIssues(unittest.TestCase):

    def testLifeCycle(self):
        r = repo.IssueRepository("twisted.issues", None)
        finder = repo.IssuePerson("customer")
        fixer = repo.IssuePerson("Simon")
        fixer2 = repo.IssuePerson("Tenth")
        for ff in finder, fixer, fixer2:
            ff.setNotifier(DummyNotifier())
        q = r.buildQueue(queueName)
        i = r.queueIssue(finder, "it doesn't work", queueName)
        q.respondToNextIssue(fixer)
        self.failUnlessEqual(len(q.issues), 0, "Queue not the right length.")
        self.failUnless(isinstance(i.states[-1], issue.InConversation), "I'm in the wrong state.")
        self.failUnlessEqual(i.states[-1].fixer, fixer, "I have the wrong fixer")
        i.setState(issue.InTransfer(fixer, fixer2))
        i.setState(issue.InConversation(fixer2))
        t = r.buildTask(fixer, "set fire to customer")
        t.addDependentIssue(i)

