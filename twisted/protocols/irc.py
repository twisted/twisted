"""Internet Relay Chat Protocol implementation
"""

from twisted.protocols import basic, protocol
import string

class IRCParseError(ValueError):
    pass

def parsemsg(s):
    # Does a prefix exist?
    if s[0] == ':':
        # If so, grab it.
        x = string.find(s,' ')
        if x == -1:
            raise IRCParseError
        prefix = s[1:x]
        s = s[x+1:]
    else:
        prefix = ''
    # Grab the command.
    x = string.find(s,' ')
    if x == -1:
        raise IRCParseError
    command = s[:x]
    s = s[x+1:]
    x = string.find(s,':')
    # Is there a "long" parameter?
    if x != -1:
        trailing = s[x+1:]
        s = s[:x]
    else:
        trailing = None
    params = string.split(s, ' ')
    if trailing is not None:
        params.append(trailing)
    return prefix, command, params

class IRC(basic.LineReceiver):
    nickname = '*'
    def connectionMade(self):
        self.channels = []

    def connectionLost(self):
        print self.nickname, "lost connection"
        if self.nickname != '*':
            del self.factory.chatters[self.nickname]
            for channel in self.channels:
                channel.chatters.remove(self)

    def irc_NICK(self, prefix, params):
        nickname = params[0]
        if not self.factory.chatters.has_key(nickname):
            if self.nickname != '*':
                del self.factory.chatters[self.nickname]
                # << NICK glyph
                # >> :testNickChange!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net NICK :glyph
                self.sendLine(":%s!nowhere NICK :%s" %(self.nickname, nickname))
            else:
                self.sendLine(":ircservice 001 %s :Welcome to Twisted" % nickname)
            self.nickname = nickname
            self.factory.chatters[nickname] = self
        else:
            self.sendLine(":ircservice 433 %s %s :Nickname is already in use." % (self.nickname, nickname))

    def irc_USER(self, prefix, params):
        self.realname = params[-1]

    def irc_JOIN(self, prefix, params):
        channame = params[0][1:]
        if self.factory.channels.has_key(channame):
            channel = self.factory.channels[channame]
        else:
            channel = ChatRoom(channame)
            self.factory.channels[channame] = channel
        channel.chatters.append(self)
        self.channels.append(channel)
        self.sendLine(":%s!nowhere JOIN :#%s" % (self.nickname,channame))
        self.irc_NAMES('', [params[0]])
        self.irc_TOPIC('', [params[0]])

    def irc_PRIVMSG(self, prefix, params):
        name = params[0]
        text = params[-1]
        if name[0] == '#':
            print 'talking to channel', self.nickname, prefix, params
            channame = name[1:]
            channel = self.factory.channels[channame]
            if channel in self.channels:
                channel.say(self, text)
        else:
            print self.factory.chatters
            chatter = self.factory.chatters[name]
            chatter.hearWhisper(self, text)
        
    def irc_PART(self, prefix, params):
        channame = params[0][1:]
        channel = self.factory.channels[channame]
        self.channels.remove(channel)
        self.sendLine(":%s!nowhere PART :#%s" % channame)

    def irc_MODE(self, prefix, params):
        name = params[0]
        print 'mode?', prefix, params
        if name[0] == '#':
            # get the channel, maybe?
            self.sendLine(":ircservice 324 %s +" % self.nickname)

    def irc_unknown(self, prefix, command, params):
        print 'unknown!'

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
        print 'topic',prefix,params
        if len(params) == 1:
            channame = params[0][1:]
            channel = self.factory.channels[channame]
            self.sendLine(":ircservice 332 %s #%s :%s" % (self.nickname, channel.name, channel.topic))
        
    def lineReceived(self, line):
        prefix, command, params = parsemsg(line)
        print prefix, command, params
        method = getattr(self, "irc_%s" % command, None)
        if method is not None:
            method(prefix, params)
        else:
            self.irc_unknown(prefix, command, params)

    def hearWhisper(self, other, text):
        #>> :glyph_!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net PRIVMSG glyph_ :hello
        #>> :glyph!glyph@adsl-64-123-27-108.dsl.austtx.swbell.net PRIVMSG glyph_ :hello

        self.sendLine(":%s!nowhere PRIVMSG %s :%s" % (other.nickname, self.nickname, text))

    def hearMsg(self, room, other, speech):
        if other is not self:
            self.sendLine(":%s!nowhere PRIVMSG #%s :%s" % (other.nickname, room.name, speech))

class ChatRoom:
    def __init__(self, name):
        self.name = name
        self.chatters = []
        self.topic = ''

    def say(self, user, message):
        for chatter in self.chatters:
            chatter.hearMsg(self, user, message)

class IRCFactory(protocol.Factory):
    def __init__(self):
        self.channels = {}
        self.chatters = {}

    def buildProtocol(self, addr):
        irc = IRC()
        irc.factory = self
        return irc

class IRCClient(basic.LineReceiver):

    def join(self, channel):
        self.sendLine("JOIN #%s" % channel)

    def say(self, channel, message):
        self.sendLine("PRIVMSG #%s :%s" % (channel, message))

    def msg(self, user, message):
        self.sendLine("PRIVMSG %s :%s" % (user, message))

    def setNick(self, nickname):
        self.nickname = nickname
        self.sendLine("NICK %s" % nickname)

    def irc_443(self, prefix, params):
        self.setNick(self.nickname+'_')

    def irc_JOIN(self, prefix, params):
        pass

    def irc_PING(self, prefix, params):
        self.sendLine("PONG %s" % params[-1])

    def irc_PRIVMSG(self, prefix, params):
        user = prefix
        channel = params[0]
        message = params[-1]
        self.privmsg(user, channel, message)

    def privmsg(self, user, channel, message):
        pass

    def irc_unknown(self, prefix, command, params):
        pass

    def lineReceived(self, line):
        prefix, command, params = parsemsg(line)
        method = getattr(self, "irc_%s" % command, None)
        if method is not None:
            method(prefix, params)
        else:
            self.irc_unknown(prefix, command, params)
