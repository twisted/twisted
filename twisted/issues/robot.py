
import string
from twisted.issues.repo import IIssueNotifier, CouldNotTranscribe
from twisted.words.service import WordsClient

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
                                              self.voice.service.application)
        self.repository = repository

    # bot methods

    def receiveDirectMessage(self, sender, message, metadata=None):
        print 'zing!'
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

    def issue_done(self, issuePerson, message):
        """I (a fixer) have finished resolving an issue.  Mark it as done.
        """
        if not message:
            if len(issuePerson.currentlyFixing) == 1:
                i = issuePerson.currentlyFixing.values()[0]
                i.setState(issue.FixerClosed())
            else:
                issuePerson.notifyText("YOU MUST SPECIFY ONE OF THE FOLLOWING ISSUES: %s"
                                       % ' '.join(issuePerson.currentlyFixing.keys()))
        else:
            issuePerson.currentlyFixing[int(message)].setState(issue.FixerClosed())

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

    def issue_next(self, issuePerson, message):
        r = self.repository
        q = r.getQueue(message)
        q.respondToNextIssue(issuePerson)
        issuePerson.notifyText("YOU HAVE RESPONDED TO AN ISSUE.")



def createBot():
    return IssueBot()
