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

# System Imports
import time
import string
import pydoc

# Twisted Imports
from twisted.issues.repo import IIssueNotifier, CouldNotTranscribe
from twisted.words.service import WordsClient
from twisted.issues.task import Task
from twisted.python import log, reflect

# Sibling Imports
import issue

class IssueBotNotifier:

    __implements__ = IIssueNotifier

    def __init__(self, issueBot, voiceName):
        self.issueBot = issueBot
        self.voiceName = voiceName

    def _getVoice(self):
        return self.issueBot.voice.service.getPerspectiveNamed(self.voiceName)
    ### IIssueNotifier

    def contactInformation(self):
        """Return a description of this notifier.

        I am a live person on chat, so I'll say so.
        """
        return "Live Person: %s" % self.voiceName

    def beginTranscribing(self, otherNotifier):
        if not isinstance(otherNotifier, IssueBotNotifier):
            raise CouldNotTranscribe(
                "The other notifier was not an issuebot notifier.")
        return self._getVoice().transcribeConversationWith(otherNotifier.voiceName)

    def notifyText(self, message):
        """Send a text notification message to the words perspective I
        represent.
        """
        self.issueBot.voice.directMessage(self.voiceName, message)

    def notifyFixerReady(self, issueFixer, issue):
        issueFixer.notifier._getVoice().directMessage(
            self.voiceName,
            "will be helping you today with issue #%s." % issue.number,
            {'style': "emote"})
        
    def notifyFixerGone(self, issueFixer, issue):
        """Notify me that the fixer who I was talking to has reclassified the
        issue.
        """
        issueFixer.notifier._getVoice().directMessage(
            self.voiceName,
            "Thanks for using twisted.issues!  Your issue, #%s, has been reclassified as %s." %
            (issue.number, issue.getStatusMessage()))

    def notifyFinderReady(self, issueFinder, issue):
        issueFinder.notifier._getVoice().directMessage(
            self.voiceName,
            "SESSION STARTING: reporting issue #%s: %r" % (issue.number, issue.comments[0][1]))

    def notifyFinderGone(self, issueFinder, issue):
        """Notify me that the finder who I was talking to has reclassified the
        issue.
        """
        issueFinder.notifier._getVoice().directMessage(
            self.voiceName,
            "SESSION ENDING: issue #%s: %r: reclassified as: %s" % (
            issue.number, issue.comments[0][1], issue.getStatusMessage()))



class IssueBot(WordsClient):
    # setup bot

    protoServiceName = "twisted.issues"

    def setupBot(self, voice, repository=None):
        import repo
        self.voice = voice
        self.voiceToPerson = {}
        if repository is None:
            repository = repo.IssueRepository(self.protoServiceName,
                                              self.voice.service.serviceParent,
                                              self.voice.service.authorizer)
        self.repository = repository

    # bot methods

    def receiveDirectMessage(self, sender, message, metadata=None):
        cmds = string.split(message, maxsplit=1)
        command = cmds[0]
        args = (len(cmds)>1 and cmds[1]) or ''
        if self.voiceToPerson.has_key(sender):
            issuePerson = self.voiceToPerson[sender]
        else:
            self.voice.directMessage(sender,
                                     "YOU ARE BEING REGISTERED, "
                                     "PLEASE DO NOT MOVE, THE RETINAL PROBE "
                                     "WILL BE PAINLESS.")
            issuePerson = self.repository.createPerspective(sender)
            self.voiceToPerson[sender] = issuePerson
            issuePerson.setNotifier(IssueBotNotifier(self, sender))
            # self.voice.addContact(sender)
            self.voice.directMessage(sender,
                                     "THANK YOU FOR YOUR COOPERATION.  "
                                     "REMEMBER, WE'RE ALL IN THIS TOGETHER.")
        method = getattr(self, "issue_%s" % command, None)
        if method:
            method(issuePerson, args)
        else:
            self.voice.directMessage(sender, "I DID NOT UNDERSTAND YOUR QUERY.")

    # issuebot methods

    def getMyIssue(self, issuePerson, message):
        if not message:
            if len(issuePerson.currentlyFixing) == 1:
                return issuePerson.currentlyFixing.values()[0]
            else:
                issuePerson.notifyText(
                    "YOU MUST SPECIFY ONE OF THE FOLLOWING ISSUES: %s"
                    % ' '.join(issuePerson.currentlyFixing.keys()))
        else:
            return issuePerson.currentlyFixing[int(message)]

    def issue_done(self, issuePerson, message):
        """I (a fixer) have finished resolving an issue.  Mark it as done.
        """
        i = self.getMyIssue(issuePerson, message) # XXX maybe this should be global?
        if i:
            i.setState(issue.FixerClosed())

    def issue_transfer(self, issuePerson, message):
        """Transfer an issue to another support representative.
        """
        l = message.split(" ", 1)
        if len(l) == 2:
            issuenum, personName = l
        else:
            issuenum = ''
            personName = message
        i = self.getMyIssue(issuePerson, issuenum)
        if i:
            otherPerson = self.voiceToPerson[personName]
            i.setState(issue.InTransfer(issuePerson, otherPerson))

    def issue_accept(self, issuePerson, message):
        """Accept the transfer of an issue (UNIMPLEMENTED.)
        """

    def issue_complain(self, issuePerson, message):
        """Complain about an issue.
        """
        r = self.repository
        r.queueIssue(issuePerson, message)
        issuePerson.notifyText("A SUPPORT REPRESENTATIVE WILL BE WITH YOU SHORTLY.")

    def issue_listen(self, issuePerson, message):
        """Listen for new issues on a queue.
        """
        r = self.repository
        q = r.getQueue(message)
        q.addListeningFixer(issuePerson)
        issuePerson.notifyText("YOU ARE NOW LISTENING ON %r."% message)

    ## Comments

    def _loadIssueAnd(self, issueNumber, issuePerson, callback, *args, **kw):
        self.repository.loadIssue(int(issueNumber)).addCallbacks(
            callback,self._ebLoadIssue, callbackArgs=(issuePerson,)+args,
            callbackKeywords=kw, errbackArgs=(issueNumber,issuePerson))
    def _ebLoadIssue(self, failure, issueNumber, issuePerson):
        issuePerson.notifyText("no such issue: #%s" % issueNumber)

    def issue_comment(self, issuePerson, message):
        """Add a comment to an existing issue.
        """
        number, comment = message.split(" ", 1)
        self._loadIssueAnd(number, issuePerson, self._cbCommentIssue, comment)

    def _cbCommentIssue(self, issue, issuePerson, comment):
        issue.addComment(issuePerson, comment)
        issuePerson.notifyText("Added comment.")

    def issue_showlogs(self, issuePerson, message):
        """Show logs for an existing issue.
        """
        i = self.repository.issues[int(message)] # XXX cheating
        for state in i.states:
            if hasattr(state, 'transcript'):
                for tim, vname, message, metadata in state.transcript.chat:
                    issuePerson.notifyText("%s <%s> %s" % (tim, vname, message))

    def issue_list(self, issuePerson, message):
        """List issues in a specified queue.
        """
        q = self.repository.getQueue(message)
        now = time.time()
        for issue in q.issues:
            t = issue.comments[0][2] # time
            minutes = int((now - t) / (60)) % 60
            hours = int((now - t) / (60 * 60))
            issuePerson.notifyText("#%s - %0.2d:%0.2d - %s - %s" % (
                issue.number, hours, minutes,
                issue.getFinder().perspectiveName,
                issue.comments[0][1]
                ))

    def issue_next(self, issuePerson, message):
        """Pull the next issue out of a specified queue.
        """
        if message:
            qname = message
        else:
            qname = 'default'
        r = self.repository
        q = r.getQueue(qname)
        q.respondToNextIssue(issuePerson)
        issuePerson.notifyText("YOU HAVE RESPONDED TO AN ISSUE.")

    def issue_needstask(self, issuePerson, message):
        """Flag an issue as needing a task, and create a new task for it.
        """
        number, taskcomment = message.split(' ', 1)
        self._loadIssueAnd(number, issuePerson, self._cbNeedsTask, taskcomment)

    def _cbNeedsTask(self, issue, issuePerson, taskcomment):
        t = self.repository.buildTask(issuePerson, taskcomment)
        t.addDependentIssue(issue)
        issuePerson.notifyText("ADDED")

    # meta

    def issue_hello(self, issuePerson, message):
        """Greet me.
        """
        issuePerson.notifyText("Hello!  I am a chatterbot interface to the twisted.issues issue tracking and live support system.  If you need help, try saying 'help'.  Have a nice day!")

    def issue_help(self, issuePerson, message):
        """Get help with this bot.
        """
        if message:
            try:
                method = getattr(self, "issue_"+message)
            except AttributeError:
                issuePerson.notifyText("No such command %r" % message)
                return
            doc = method.__doc__ or ''
            issuePerson.notifyText("help on %r: %s" %
                                   (method.__name__.split('_', 1)[1],
                                    doc.strip()))
            return
        
        issuePerson.notifyText("Here is a brief summary of all the commands I support:")
        mymethods = reflect.prefixedMethods(self, "issue_")
        for method in mymethods:
            disc, name = method.__name__.split('_', 1)
            if method.__doc__:
                docco = pydoc.splitdoc(method.__doc__)[0]
            else:
                docco = '<undocumented>'
            issuePerson.notifyText("%s: %s" % (name, docco))

def createBot():
    return IssueBot()
