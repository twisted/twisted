from twisted.protocols import irc, protocol

class IRCChatter(irc.IRC):
    nickname = '*'
    participant = None
    def hearWhisper(self, other, text):
        #>> :glyph_!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net PRIVMSG glyph_ :hello
        #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net PRIVMSG glyph_ :hello

        self.sendLine(":%s!nowhere PRIVMSG %s :%s" % (other.nickname, self.nickname, text))

    def hearMsg(self, room, other, speech):
        if other is not self:
            self.sendLine(":%s!nowhere PRIVMSG #%s :%s" % (other.nickname, room.name, speech))

    def connectionLost(self):
        log.msg( "%s lost connection" % self.nickname )
        if self.participant:
            self.participant.detached(self)

    def irc_USER(self, prefix, params):
        """Set your username.  This is not relevant.
        """
        self.realname = params[-1]

    def irc_NICK(self, prefix, params):
        """Set your nickname.
        """
        nickname = params[0]
        if not self.participant:
            # << NICK glyph
            # >> :testNickChange!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net NICK :glyph
            # self.sendLine(":%s!nowhere NICK :%s" %(self.nickname, nickname))
            try:
                participant = self.service.getPerspectiveNamed(nickname)
            except KeyError:
                self.sendLine(":ircservice 433 %s %s :this username is invalid" % (self.nickname, nickname))
                self.transport.loseConnection()
            else:
                self.sendLine(":ircservice 001 %s :connected to Twisted IRC" % (nickname))
                self.sendLine(":login!s@Login NOTICE %s :You 'must /msg login <your password>' to use this server" % nickname)
                self.nickname = nickname
                self.pendingLogin = participant
        else:
            self.sendLine(":ircservice 433 %s %s :this username is invalid" % (self.nickname, nickname))

    def irc_PRIVMSG(self, prefix, params):
        """Send a message.
        """
        name = params[0]
        text = params[-1]
        if self.perspective:
            print 'privmsg oops'
            if name[0] == '#':
                log.msg( 'talking to channel %s %s %s ' % (self.nickname, prefix, params ))
                channame = name[1:]
                channel = self.factory.channels[channame]
                if channel in self.channels:
                    channel.say(self, text)
            else:
                chatter = self.factory.chatters[name]
                chatter.hearWhisper(self, text)
        else:
            if name == 'login':
                self.service.check(self.nickname, text)
                self.pendingLogin = self.participant

    def irc_JOIN(self, prefix, params):
        channame = params[0][1:]
        if self.factory.channels.has_key(channame):
            channel = self.factory.channels[channame]
        else:
            channel = ChatRoom(channame)
            self.factory.channels[channame] = channel
        channel.chatters.append(self)
        self.channels.append(channel)
        for chatter in channel.chatters:
            chatter.sendLine(":%s!nowhere JOIN :#%s" % (self.nickname,channame))
        self.irc_NAMES('', [params[0]])
        self.irc_TOPIC('', [params[0]])

    def irc_PART(self, prefix, params):
        channame = params[0][1:]
        channel = self.factory.channels[channame]
        self.channels.remove(channel)
        for chatter in channel.chatters:
            chatter.sendLine(":%s!nowhere PART :#%s" % (self.nickname, channame))
        channel.chatters.remove(self)


    def irc_MODE(self, prefix, params):
        name = params[0]
        log.msg( 'mode? %s %s' % (prefix, params))
        if name[0] == '#':
            # get the channel, maybe?
            self.sendLine(":ircservice 324 %s +" % self.nickname)

    def irc_unknown(self, prefix, command, params):
        log.msg( 'unknown irc proto msg!' )

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
            channel = self.factory.channels[channame]
            for chatter in channel.chatters:
                self.sendLine(":ircservice 352 %s #%s nobody nowhere ircservice %s H :0 %s" % (self.nickname, channame, chatter.nickname, chatter.nickname))
            self.sendLine(":ircservice 315 %s #%s :End of /WHO list." % (self.nickname,channame))

    def irc_NAMES(self, prefix, params):
        #<< NAMES #python
        #>> :benford.openprojects.net 353 glyph = #python :Orban Taranis Aquarius maglev Supbopt nejucomo GabeW h3x @glyph MetaCosm DavidC_ moshez slipjack juri Yhg1s snibril CHarrison dalf diseaser Rainy-Day ElBarono Acapnotic helot mitiege churchr Krelin sayke Bram spiv thirmite dash draco Jii h3o_ skin_pup jaska solomon ry xmir wac rik maxter moro Nafai tpck timmy Zymurgy skreech
        #>> :benford.openprojects.net 366 glyph #python :End of /NAMES list.
        channame = params[-1][1:]
        channel = self.factory.channels[channame]
        self.sendLine(":ircservice 353 %s = #%s :%s" %
                      (self.nickname, channame,
                       string.join(map(lambda x: x.nickname, channel.chatters))))
        self.sendLine(":ircservice 366 %s #%s :End of /NAMES list." %
                      (self.nickname, channel.name))

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
            channel = self.factory.channels[channame]
            self.sendLine(":ircservice 332 %s #%s :%s" % (self.nickname, channel.name, channel.topic))
        else:
            #<< TOPIC #qdf :test
            #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net TOPIC #qdf :test
            channame = params[0][1:]
            newTopic = params[-1]
            channel = self.factory.channels[channame]
            channel.topic = newTopic
            for chatter in channel.chatters:
                chatter.sendLine(":%s!nowhere TOPIC #%s :%s" % (self.nickname, channame, newTopic))


class IRCGateway(protocol.Factory):
    def __init__(self, service):
        self.service = service
    def buildProtocol(self, connection):
        """Build an IRC protocol to talk to my chat service.
        """
        i = IRCChatter()
        i.service = self.service


