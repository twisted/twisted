
# System Imports
import string

# Twisted Imports
from twisted.protocols import irc, protocol
from twisted.spread import pb
from twisted.python import log

# sibling imports
import service

class IRCChatter(irc.IRC):
    nickname = '*'
    participant = None
    pendingLogin = None
    hostname = "nowhere"
    servicename = "twisted"

    def receiveContactList(self, contactList):
        for name, status in contactList:
            self.notifyStatusChanged(name, status)

    def notifyStatusChanged(self, name, status):
        self.receiveDirectMessage(
            "*contact*",
            "%s is %s" % (name,service.statuses[status]))

    def memberJoined(self, member, group):
        #>> :glyph_!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net JOIN :#python
        self.sendLine(":%s!%s@%s JOIN :#%s" %
                      (member, member, self.servicename, group))

    def memberLeft(self, member, group):
        #>> :glyph_!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net PART #python :test
        self.sendLine(":%s!%s@%s PART #%s :(leaving)" %
                      (member, member, self.servicename, group))


    def receiveDirectMessage(self, senderName, message):
        #>> :glyph_!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net PRIVMSG glyph_ :hello
        #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net PRIVMSG glyph_ :hello

        self.sendLine(":%s!%s@%s PRIVMSG %s :%s" %
                      (senderName, senderName, self.servicename,
                       self.nickname, message))


    def receiveGroupMessage(self, sender, group, message):
        if sender is not self:
            self.sendLine(":%s!%s@%s PRIVMSG #%s :%s" %
                          (sender, sender, self.servicename, group, message))


    def connectionLost(self):
        log.msg( "%s lost connection" % self.nickname )
        if self.participant:
            self.participant.detached(self)


    def irc_USER(self, prefix, params):
        """Set your realname.

        Simply for backwards compatibility to IRC clients.
        """
        self.realname = params[-1]


    def irc_NICK(self, prefix, params):
        """Set your nickname.
        """
        nickname = params[0]
        if not self.participant and not self.pendingLogin:
            # << NICK glyph
            # >> :testNickChange!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net NICK :glyph
            # self.sendLine(":%s!nowhere NICK :%s" %(self.nickname, nickname))
            try:
                participant = self.service.getPerspectiveNamed(nickname)
            except KeyError:
                self.sendLine(":%s 433 %s %s :this username is invalid" %
                              (self.servicename, self.nickname, nickname))
                self.transport.loseConnection()
            else:
                self.sendLine(":%s 001 %s :connected to Twisted IRC" %
                              (self.servicename, nickname))
                self.nickname = nickname
                self.receiveDirectMessage("*login*", "Password?")
##                self.sendLine(":*login*!*login*@%s NOTICE %s :You 'must /msg *login* <your password>' to use this server" %
##                              (self.servicename, nickname))
                self.pendingLogin = participant
        else:
            self.sendLine(":%s 433 %s %s :this username is invalid" %
                          (self.servicename, self.nickname, nickname))

    def irc_PRIVMSG(self, prefix, params):
        """Send a message.
        """
        name = params[0]
        text = params[-1]
        if self.participant:
            if name == '*contact*':
                # crude contacts interface
                cmds = string.split(text, ' ', 1)
                if cmds[0] == 'add':
                    self.participant.addContact(cmds[1])
                elif cmds[0] == 'remove':
                    self.participant.removeContact(cmds[1])
                else:
                    self.receiveDirectMessage("*contact*", "unknown command")
            elif name[0] == '#':
                log.msg( 'talking to channel %s %s %s ' % (self.nickname, prefix, params ))
                channame = name[1:]
                try:
                    self.participant.groupMessage(channame, text)
                except pb.Error, e:
                    self.receiveDirectMessage("*error*", str(e))
                    print 'error chatting to channel:',str(e)
            else:
                try:
                    self.participant.directMessage(name, text)
                except (KeyError, pb.Error):
                    ### << PRIVMSG vasdfasdf :hi
                    ### >> :niven.openprojects.net 401 glyph vasdfasdf :No such nick/channel
                    self.sendLine(":%s 401 %s %s :No such nick/channel" %
                                  (self.servicename, self.nickname, name))

        else:
            if name == '*login*':
                self.service.check(self.nickname, text)
                self.participant = self.pendingLogin
                self.receiveDirectMessage(
                    "*login*",
                    "Login accepted.  Welcome to %s." % self.servicename)
                self.participant.attached(self)
            else:
                self.receiveDirectMessage("*login*", "You haven't logged in yet.")
                


    def irc_JOIN(self, prefix, params):
        channame = params[0][1:]
        self.participant.joinGroup(channame)
        self.memberJoined(self.nickname, channame)
        self.irc_NAMES('', [params[0]])
        self.irc_TOPIC('', [params[0]])

    def irc_PART(self, prefix, params):
        #<< PART #java :test
        #>> :niven.openprojects.net 442 glyph #java :You're not on that channel
        channame = params[0][1:]
        print 'trying to part', channame
        try:
            self.participant.leaveGroup(channame)
        except pb.Error, e:
            self.sendLine(
                ":%s 442 %s #%s :%s" %
                (self.servicename, self.nickname, channame, str(e)))
        else:
            self.memberLeft(self.nickname, channame)

    def irc_MODE(self, prefix, params):
        name = params[0]
        log.msg('mode? %s %s' % (prefix, params))
        if name[0] == '#':
            # get the channel, maybe?
            self.sendLine(":%s 324 %s +" %
                          (self.servicename, self.nickname))

    def irc_unknown(self, prefix, command, params):
        log.msg('unknown irc proto msg!')

    def irc_WHO(self, prefix, params):
        #<< who #python
        #>> :benford.openprojects.net 352 glyph #python aquarius pc-62-31-193-114-du.blueyonder.co.uk forward.openprojects.net Aquarius H :3 Aquarius
        # ...
        #>> :benford.openprojects.net 352 glyph #python foobar europa.tranquility.net benford.openprojects.net skreech H :0 skreech
        #>> :benford.openprojects.net 315 glyph #python :End of /WHO list.
        ### also
        #<< who glyph
        #>> :benford.openprojects.net 352 glyph #python glyph adsl-64-123-27-108.dsl.austtx.swbell.net benford.openprojects.net glyph H :0 glyph
        #>> :benford.openprojects.net 315 glyph glyph :End of /WHO list.
        name = params[0]
        if name[0] == '#':
            channame = name[1:]
            group = self.service.getGroup(channame)
            for member in group.members:
                self.sendLine(
                    ":%s 352 %s #%s %s %s %s %s H :0 %s" %
                    (self.servicename, self.nickname, group.name,
                     member.name, self.servicename, self.servicename,
                     member.name, member.name))
            self.sendLine(":%s 315 %s #%s :End of /WHO list." %
                          (self.servicename, self.nickname, group.name))
        else:
            raise NotImplementedError("user 'who' not implemented")

    def irc_NAMES(self, prefix, params):
        #<< NAMES #python
        #>> :benford.openprojects.net 353 glyph = #python :Orban ... @glyph ... Zymurgy skreech
        #>> :benford.openprojects.net 366 glyph #python :End of /NAMES list.
        channame = params[-1][1:]
        group = self.service.groups.get(channame)
        if group:
            self.sendLine(":%s 353 %s = #%s :%s" %
                          (self.servicename, self.nickname, channame,
                           string.join(map(lambda member: member.name,
                                           group.members))))
        self.sendLine(":%s 366 %s #%s :End of /NAMES list." %
                      (self.servicename, self.nickname, group.name))

    def irc_TOPIC(self, prefix, params):
        #<< TOPIC #python
        #>> :benford.openprojects.net 332 glyph #python :<churchr> I really did. I sprained all my toes.
        #>> :benford.openprojects.net 333 glyph #python itamar|nyc 994713482
        ### and
        #<< TOPIC #divunal :foo
        #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net TOPIC #divunal :foo
        log.msg('topic %s %s' % (prefix, params))
        if len(params) == 1:
            channame = params[0][1:]
            group = self.service.groups[channame]
            self.sendLine(
                ":%s 332 %s #%s :%s" %
                (self.servicename, self.nickname, group.name, group.topic))
            self.sendLine(
                ":%s 333 %s #%s %s %s" %
                (self.servicename, self.nickname,
                 group.name, "god", "1"))
        else:
            #<< TOPIC #qdf :test
            #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net TOPIC #qdf :test
            raise NotImplementedError("can't change topic yet")
##            for chatter in channel.chatters:
##                chatter.sendLine(":%s!%s TOPIC #%s :%s" % (
##                    self.nickname, self.servicename, channame, newTopic))


class IRCGateway(protocol.Factory):
    def __init__(self, service):
        self.service = service
    def buildProtocol(self, connection):
        """Build an IRC protocol to talk to my chat service.
        """
        i = IRCChatter()
        i.service = self.service
        return i


