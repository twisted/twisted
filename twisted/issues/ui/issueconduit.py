"""
type, before the night overtakes you!

two Policy shims from issues; one for fixers, one for finders

communicates with machinery that handles issue InConversation state

state transition -> change Policy
InTransfer yields 'please hold' msgs
Done yields "were you happy with that" msgs

"""
from twisted.web import wmvc, server 
from twisted.python import components
from twisted.words.service import WordsClient, IWordsClient, IWordsPolicy
from twisted.issues import repo, robot

class ConduitPolicy:
    __implements__ = IWordsPolicy
    fixerNick = "sam"
    def __init__(self, voice, notifier):
        self.voice = voice
        self.notifier = notifier
    def getNameFor(self, voice):
        if self.notifier.fixer and voice is self.notifier.fixer.notifier._getVoice():
            return self.fixerNick
        else:
            return voice.name
    def lookUpParticipant(self, nick):
        if nick == self.fixerNick:
            return self.notifier.fixer.notifier._getVoice()
        else:
            return self.voice.service.getPerspectiveNamed(nick)

class ConduitNotifier(robot.IssueBotNotifier):
    __implements__ = repo.IIssueNotifier
    fixer = None
    def contactInformation(self):
        return "Hapless Web User"
    def notifyFixerReady(self, issueFixer, issue):
        self.fixer = issueFixer
        self.conduit.recipient = issueFixer.perspectiveName
        robot.IssueBotNotifier.notifyFixerReady(self, issueFixer, issue)

    def notifyFixerGone(self, issueFixer, issue):
        robot.IssueBotNotifier.notifyFixerGone(self, issueFixer, issue)
        self.fixer = None
        self.conduit.recipient = "IssueBot"
        self.conduit.die()
    
        
class IConduitSession(components.Interface):
    """
    A unique session namespace for the conduit.
    """
    def setRequest(request):
        """Set the web request object to which output written to this conduit will be sent.
        Until this is called, output will be cached; after this is called, the behavior of calling
        it again is undefined.
        """
    
    def input(arg):
        """Send input to the conduit.
        """
    
    def output(arg):
        """Send output from the conduit to the web browser.
        """

class ChatConduitSession(WordsClient):
    
    __implements__ = IConduitSession, IWordsClient
    id = 0
    
    def __init__(self, session):
        self.session = session
        self.complained = 0
        self.recipient = "IssueBot"
        ChatConduitSession.id += 1
        self.cached = []
        self.request = None
        self.name = "webchat%s" % self.id
        session.notifyOnExpire(self.die)
        self.service = None

        
    def die(self):
        self.service.deleteBot(self)
        self.session.removeComponent(IConduitSession)
        if self.request:
            self.request.finish()

    def setRequest(self, request):        
        self.request = request
        for item in self.cached:
            self.output(item)

    def setModel(self, model):
        # TODO: maybe a sanity check...?
        if not self.service:
            self.service = model.wordsService
            self.issueRepo = model.issueRepo
            self.service.addBot(self.name, self)

    def setupBot(self, voice):

        self.voice = voice

        # get the repo, create a perspective, get the issuebot, add
        # our notifier, add our policy to the notifier, tell the
        # notifier about ourself, put it in the issuebot's
        # voiceToPerson, eat the path.  EAT THE PATH.

        repository = self.issueRepo
        issuePerson = repository.createPerspective(self.name)
        issuebot = filter(lambda x: isinstance(x, robot.IssueBot),
                          self.service.bots)[0]
        self.notifier = ConduitNotifier(issuebot, self.name)
        self.notifier.conduit = self
        issuePerson.setNotifier(self.notifier)
        voice.policy = ConduitPolicy(self.voice, self.notifier)
        issuebot.voiceToPerson[self.name] = repository.createPerspective(self.name)
        issuebot.voiceToPerson[self.name].setNotifier(self.notifier)
        
    def receiveDirectMessage(self, sender, message, metadata):
        self.output("&lt;%s&gt; %s" % (sender, message))

    def input(self, arg):
        #self.recipient = self.request.args.get("recipient", [None])[0]
        # cheap hack to impress people with
        if self.recipient == "IssueBot":
            if self.complained:
                self.output("PLEASE WAIT")
            else:
                self.voice.directMessage(self.recipient, "complain " + arg)
                self.complained = 1
        else:
            self.output("&gt; <i>%s</i>" % arg)
            self.voice.directMessage(self.recipient, arg)


    def output(self, arg):
        if self.request is None:
            self.cached.append(arg)
        else:
            arg = arg.replace("'", "\\'")
            self.request.write(arg+'<script language="JavaScript1.2">' + "top.recv('" + arg + "')</script>\r\n")

components.registerAdapter(ChatConduitSession, server.Session, IConduitSession)


class MWebConduit(wmvc.WModel):
    def __init__(self, wordsService, issueRepo):
        self.wordsService = wordsService
        self.issueRepo = issueRepo


class VWebConduit(wmvc.WView):
    templateFile = "conduit.html"


class CWebConduit(wmvc.WController):
    def render(self, request):
        session = request.getSession(IConduitSession)
        session.setModel(self.model)
        input = request.args.get("input", [None])[0]
        if input:
            session.input(input)
            return "<html>%s sent.</html>" % input
        output = request.args.get("output", [None])[0]
        if output:
            session.setRequest(request)
            session.output("<html>Please state the nature of your problem "
                           "in the text field below, and your question will "
                           "be answered in the order it was received.<br/>")
            # We'll never be done!
            return server.NOT_DONE_YET
        return wmvc.WController.render(self, request)


wmvc.registerViewForModel(VWebConduit, MWebConduit)
wmvc.registerControllerForModel(CWebConduit, MWebConduit)
