
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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


# System Imports
import fnmatch
import string

# Twisted Imports
from twisted.protocols import irc, protocol
from twisted.spread import pb
from twisted.python import log
from twisted import copyright
from twisted.manhole import coil

# sibling imports
import service

class IRCChatter(irc.IRC):
    nickname = '*'
    passwd = None
    participant = None
    pendingLogin = None
    hostname = "nowhere"
    servicename = "twisted.words"

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
            self.participant.detached(self, self.identity)


    def sendMessage(self, command, *parameter_list, **kw):
        if not kw.has_key('prefix'):
            kw['prefix'] = self.servicename

        if not kw.has_key('to'):
            kw['to'] = self.nickname

        arglist = [self, command, kw['to']] + list(parameter_list)
        apply(irc.IRC.sendMessage, arglist, kw)


    def irc_unknown(self, prefix, command, params):
        log.msg('unknown irc proto msg!')


    def irc_PASS(self, prefix, params):
        """Password message -- Register a password.

        Parameters: <password>

        [REQUIRED]

        Note that IRC requires the client send this *before* NICK
        and USER.
        """
        self.passwd = params[-1]


    def irc_NICK(self, prefix, params):
        """Nick message -- Set your nickname.

        Parameters: <nickname>

        [REQUIRED]

        This is also probably the first thing the client sends us
        (except possibly PASS), so the rest of the sign-on junk is in
        here.
        """

        nickname = params[0]
        if not self.participant and not self.pendingLogin:
            # << NICK glyph
            # >> :testNickChange!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net NICK :glyph
            # self.sendLine(":%s!nowhere NICK :%s" %(self.nickname, nickname))
            try:
                participant = self.service.getPerspectiveNamed(nickname)
            except service.UserNonexistantError:
                self.sendMessage(irc.ERR_ERRONEUSNICKNAME,
                                 nickname, ":this username is invalid",
                                 to=nickname)
                # XXX - We should really let them have another shot at
                # giving their nick instead of just terminating the
                # connection.
                self.transport.loseConnection()
            else:
                self.nickname = nickname
                self.sendMessage(irc.RPL_WELCOME,
                                 ":connected to Twisted IRC")
                self.sendMessage(irc.RPL_YOURHOST,
                                 ":Your host is %s, running version %s" %
                                 (self.servicename, copyright.version))
                self.sendMessage(irc.RPL_CREATED,
                                 ":This server was created %s" %
                                 "by a very sick man." or 'XXX: on date')
                # "Bummer.  This server returned a worthless 004 numeric.
                #  I'll have to guess at all the values"
                #    -- epic
                self.sendMessage(irc.RPL_MYINFO,
                                 self.servicename, copyright.version,
                                  'w', 'n') # user and channel modes
                if self.passwd is None:
                    self.receiveDirectMessage("*login*", "Password?")
                    self.pendingLogin = participant
                else:
                    self.logInAs(participant, self.passwd)
        else:
            # XXX: Is this error string appropriate?
            self.sendLine(irc.ERR_NICKNAMEINUSE,
                          nickname, ":this username is invalid")

    def logInAs(self, participant, password):
        """Spawn appropriate callbacks to log in as this participant.
        """
        self.pendingLogin = participant
        self.pendingPassword = password
        req = participant.getIdentityRequest()
        req.addCallbacks(self.loggedInAs, self.notLoggedIn)
        req.arm()

    def loggedInAs(self, ident):
        """Successfully logged in.
        """
        if ident.verifyPlainPassword(self.pendingPassword):
            self.identity = ident
            self.pendingLogin.attached(self, self.identity)
            self.participant = self.pendingLogin
            self.receiveDirectMessage("*login*", "Authentication accepted.  Thank you.")
        else:
            self.notLoggedIn("unauthorized")
        del self.pendingLogin
        del self.pendingPassword

    def notLoggedIn(self, message):
        """Login failed.
        """
        self.receiveDirectMessage("*login*", "Login failed: %s" % message)

    def irc_USER(self, prefix, params):
        """User message -- Set your realname.

        Parameters: <user> <mode> <unused> <realname>

        [REQUIRED] for backwards compatibility to IRC clients.
        """
        self.realname = params[-1]


    def irc_OPER(self, prefix, params):
        """Oper message

        Parameters: <name> <password>

        [REQUIRED]
        """
        pass


    # Note: this is *user* MODE, but we also have channel MODE
    # defined below.
    def irc_MODE(self, prefix, params):
        """User mode message

        Parameters: <nickname>
            *( ( "+" / "-" ) *( "i" / "w" / "o" / "O" / "r" ) )


        [REQUIRED]
        """
        if string.lower(params[0]) != string.lower(self.nickname):
            return self.irc_channelMODE(prefix, params)


    def irc_SERVICE(self, prefix, params):
        """Service message

        Parameters: <nickname> <reserved> <distribution> <type>

        [REQUIRED]
        """
        pass


    def irc_QUIT(self, prefix, params):
        """Quit

        Parameters: [ <Quit Message> ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_SQUIT(self, prefix, params):
        """Squit

        Parameters: <server> <comment>

        [REQUIRED]
        """
        pass


    def irc_JOIN(self, prefix, params):
        """Join message

        Parameters: ( <channel> *( "," <channel> ) [ <key> *( "," <key> ) ] )

        [REQUIRED]
        """
        try:
            channame = params[0][1:]
            self.participant.joinGroup(channame)
        except pb.Error:
            pass
        else:
            self.memberJoined(self.nickname, channame)
            self.irc_NAMES('', [params[0]])
            self.irc_TOPIC('', [params[0]])


    def irc_PART(self, prefix, params):
        """Part message

        Parameters: <channel> *( "," <channel> ) [ <Part Message> ]

        [REQUIRED]
        """
        #<< PART #java :test
        #>> :niven.openprojects.net 442 glyph #java :You're not on that channel
        channame = params[0][1:]
        print 'trying to part', channame
        try:
            self.participant.leaveGroup(channame)
        except pb.Error, e:
            self.sendMessage(irc.ERR_NOTONCHANNEL,
                             "#%s :%s" % (channame, e))
        else:
            self.memberLeft(self.nickname, channame)


    # Channel mode, in contrast to setting user mode, defined in
    # irc_MODE above.  (That MODE passes the call to this one if the
    # first parameter is not the user's nick.)
    def irc_channelMODE(self, prefix, params):
        """Channel mode message

        Parameters: <channel> *( ( "-" / "+" ) *<modes> *<modeparams> )

        [REQUIRED]
        """
        name = params[0]
        log.msg('mode? %s %s' % (prefix, params))
        if name[0] == '#':
            # get the channel, maybe?
            self.sendMessage(irc.RPL_CHANNELMODEIS, name, "+")


    def irc_TOPIC(self, prefix, params):
        """Topic message

        Parameters: <channel> [ <topic> ]

        [REQUIRED]
        """
        #<< TOPIC #python
        #>> :benford.openprojects.net 332 glyph #python :<churchr> I really did. I sprained all my toes.
        #>> :benford.openprojects.net 333 glyph #python itamar|nyc 994713482
        ### and
        #<< TOPIC #divunal :foo
        #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net TOPIC #divunal :foo
        log.msg('topic %s %s' % (prefix, params))
        if len(params) == 1:
            if params[0][0] != '#':
                self.receiveDirectMessage("*error*", "invalid channel name")
                return
            channame = params[0][1:]
            group = self.service.getGroup(channame)
            self.sendMessage(irc.RPL_TOPIC,
                             "#" + group.name, ":" + group.topic)
            self.sendMessage('333', # not in the RFC
                             "#" + group.name, "god", "1")
        else:
            #<< TOPIC #qdf :test
            #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net TOPIC #qdf :test
            #raise NotImplementedError("can't change topic yet")
            self.receiveDirectMessage("*error*", "topic change not implemented")
##            for chatter in channel.chatters:
##                chatter.sendLine(":%s!%s TOPIC #%s :%s" % (
##                    self.nickname, self.servicename, channame, newTopic))


    def irc_NAMES(self, prefix, params):
        """Names message

        Parameters: [ <channel> *( "," <channel> ) [ <target> ] ]

        [REQUIRED]
        """
        #<< NAMES #python
        #>> :benford.openprojects.net 353 glyph = #python :Orban ... @glyph ... Zymurgy skreech
        #>> :benford.openprojects.net 366 glyph #python :End of /NAMES list.
        channame = params[-1][1:]
        group = self.service.groups.get(channame)
        if group:
            # XXX - need to make sure this doesn't exceed the 512
            # character limit.  If so, send it in multiple lines.
            self.sendMessage(irc.RPL_NAMREPLY, "=", "#" + channame,
                          ":" +
                          string.join(map(lambda member: member.name,
                                          group.members)))
        self.sendMessage(irc.RPL_ENDOFNAMES,
                         "#" + channame, ":End of /NAMES list.")


    def irc_LIST(self, prefix, params):
        """List message

        Parameters: [ <channel> *( "," <channel> ) [ <target> ] ]

        [REQUIRED]
        """
        log.msg('list %s %s' % (prefix, params))

##        if params:
##            group_masks = map(string.lower, string.split(params[0], ','))
##            for mask in group.masks:
##                if len(mask) > 1 and mask[0] in '#!+&':
##                    mask = mask[1:]
##        else:
##            group_masks = ['*']

##        for group_name, group in self.service.groups.items():
##            group_lname = string.lower(group_name)
##            for mask in group_masks:
##                if fnmatch.fnmatch(group_lname, mask):
##                    it_matches = 1
##                    break
##            if it_matches:
##                self.sendMessage(irc.RPL_LIST, group_name,
##                                 str(len(group.members)),
##                                 ":" + group.topic)
        self.sendMessage(irc.RPL_LISTEND, ":End of LIST")


    def irc_INVITE(self, prefix, params):
        """Invite message

        Parameters: <nickname> <channel>

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_KICK(self, prefix, params):
        """Kick command

        Parameters: <channel> *( "," <channel> ) <user> *( "," <user> )

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_PRIVMSG(self, prefix, params):
        """Send a (private) message.

        Parameters: <msgtarget> <text to be sent>

        [REQUIRED]
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
                except service.WordsError, e:
                    ### << PRIVMSG vasdfasdf :hi
                    ### >> :niven.openprojects.net 401 glyph vasdfasdf :No such nick/channel
                    self.sendMessage(irc.ERR_NOSUCHNICK, name,
                                     ":%s" % (e,))
        else:
            if name == '*login*':
                self.logInAs(self.pendingLogin, text)
            else:
                self.receiveDirectMessage("*login*", "You haven't logged in yet.")



    def irc_NOTICE(self, prefix, params):
        """Notice

        Parameters: <msgtarget> <text>

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_MOTD(self, prefix, params):
        """Motd message

        Parameters: [ <target> ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_LUSERS(self, prefix, params):
        """Lusers message

        Parameters: [ <mask> [ <target> ] ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_VERSION(self, prefix, params):
        """Version message

        Parameters: [ <target> ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_STATS(self, prefix, params):
        """Stats message

        Parameters: [ <query> [ <target> ] ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_LINKS(self, prefix, params):
        """Links message

        Parameters: [ [ <remote server> ] <server mask> ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_TIME(self, prefix, params):
        """Time message

        Parameters: [ <target> ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_CONNECT(self, prefix, params):
        """Connect message

        Parameters: <target server> <port> [ <remote server> ]

        [REQUIRED]
        """
        pass


    def irc_TRACE(self, prefix, params):
        """Trace message

        Parameters: [ <target> ]

        [REQUIRED]
        """
        pass


    def irc_INFO(self, prefix, params):
        """Admin command

        Parameters: [ <target> ]

        [REQUIRED]
        """
        pass


    def irc_SERVLIST(self, prefix, params):
        """Servlist message

        Parameters: [ <mask> [ <type> ] ]

        [REQUIRED]
        """
        pass


    def irc_SQUERY(self, prefix, params):
        """Squery

        Parameters: <servicename> <text>

        [REQUIRED]
        """
        pass


    def irc_WHO(self, prefix, params):
        """Who query

        Parameters: [ <mask> [ "o" ] ]

        [REQUIRED]
        """
        #<< who #python
        #>> :benford.openprojects.net 352 glyph #python aquarius pc-62-31-193-114-du.blueyonder.co.uk forward.openprojects.net Aquarius H :3 Aquarius
        # ...
        #>> :benford.openprojects.net 352 glyph #python foobar europa.tranquility.net benford.openprojects.net skreech H :0 skreech
        #>> :benford.openprojects.net 315 glyph #python :End of /WHO list.
        ### also
        #<< who glyph
        #>> :benford.openprojects.net 352 glyph #python glyph adsl-64-123-27-108.dsl.austtx.swbell.net benford.openprojects.net glyph H :0 glyph
        #>> :benford.openprojects.net 315 glyph glyph :End of /WHO list.
        if not params:
            self.sendMessage(irc.RPL_ENDOFWHO, ":/WHO not supported.")
            return
        name = params[0]
        if name[0] == '#':
            channame = name[1:]
            group = self.service.getGroup(channame)
            for member in group.members:
                self.sendMessage(irc.RPL_WHOREPLY, "#" + group.name,
                                 member.name, self.servicename,
                                 self.servicename, member.name,
                                 "H",":0", member.name)
            self.sendMessage(irc.RPL_ENDOFWHO, "#" + group.name,
                             ":End of /WHO list.")
        else:
            self.sendLine(irc.RPL_ENDOFWHO, ":User /WHO not implemented")


    def irc_WHOIS(self, prefix, params):
        """Whois query

        Parameters: [ <target> ] <mask> *( "," <mask> )

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_WHOWAS(self, prefix, params):
        """Whowas

        Parameters: <nickname> *( "," <nickname> ) [ <count> [ <target> ] ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_KILL(self, prefix, params):
        """Kill message

        Parameters: <nickname> <comment>

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_PING(self, prefix, params):
        """Ping message

        Parameters: <server1> [ <server2> ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_PONG(self, prefix, params):
        """Pong message

        Parameters: <server> [ <server2> ]

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_ERROR(self, prefix, params):
        """Error

        Parameters: <error message>

        [REQUIRED]
        """
        pass # XXX - NotImplementedError


    def irc_AWAY(self, prefix, params):
        """Away

        Parameters: [ <text> ]

        [Optional]
        """
        pass


    def irc_REHASH(self, prefix, params):
        """Rehash message

        Parameters: None

        [Optional]
        """
        pass


    def irc_DIE(self, prefix, params):
        """Die message

        Parameters: None

        [Optional]
        """
        pass


    def irc_RESTART(self, prefix, params):
        """Restart message

        Parameters: None

        [Optional]
        """
        pass


    def irc_SUMMON(self, prefix, params):
        """Summon message

        Parameters: <user> [ <target> [ <channel> ] ]

        [Optional]
        """
        pass


    def irc_USERS(self, prefix, params):
        """Users

        Parameters: [ <target> ]

        [Optional]
        """
        pass


    def irc_WALLOPS(self, prefix, params):
        """Operwall message

        Parameters: <Text to be sent>

        [Optional]
        """
        pass


    def irc_USERHOST(self, prefix, params):
        """Userhost message

        Parameters: <nickname> *( SPACE <nickname> )

        [Optional]
        """
        pass


    def irc_ISON(self, prefix, params):
        """Ison message

        Parameters: <nickname> *( SPACE <nickname> )

        [Optional]
        """
        pass


class IRCGateway(protocol.Factory, coil.Configurable):
    configCreatable = 0
    def __init__(self, service):
        self.service = service
    def buildProtocol(self, connection):
        """Build an IRC protocol to talk to my chat service.
        """
        i = IRCChatter()
        i.service = self.service
        return i

coil.registerClass(IRCGateway)
