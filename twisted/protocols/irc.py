"""Internet Relay Chat Protocol implementation
"""

from twisted.protocols import basic, protocol
from twisted.python import log
import string

class IRCParseError(ValueError):
    pass

def parsemsg(s):
    prefix = ''
    trailing = []
    if s[0] == ':':
        prefix, s = string.split(s[1:], maxsplit=1)
    if string.find(s,':') != -1:
        s, trailing = string.split(s, ':', 1)
        args = string.split(s)
        args.append(trailing)
    else:
        args = string.split(s)
    command = args.pop(0)
    return prefix, command, args


class IRC(protocol.Protocol):
    nickname = '*'
    buffer = ""
    
    def connectionMade(self):
        log.msg("irc connection made")
        self.channels = []

    def sendLine(self, line):
        self.transport.write(line+"\r\n")

    def dataReceived(self, data):
        """ This hack is to support mIRC, which sends LF only, even though the
        RFC says CRLF.  (Also, the flexibility of LineReceiver to turn "line
        mode" on and off was not required.)
        """
        log.msg( "data: %s" % repr(data) )
        self.buffer = self.buffer + data
        lines = string.split(self.buffer, "\n") # get the lines
        self.buffer = lines.pop() # pop the last element (we're not sure it's a line)
        for line in lines:
            if line[-1] == "\r":
                line = line[:-1]
            self.lineReceived(line)

    def connectionLost(self):
        log.msg( "%s lost connection" % self.nickname )
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
        for chatter in channel.chatters:
            chatter.sendLine(":%s!nowhere JOIN :#%s" % (self.nickname,channame))
        self.irc_NAMES('', [params[0]])
        self.irc_TOPIC('', [params[0]])

    def irc_PRIVMSG(self, prefix, params):
        name = params[0]
        text = params[-1]
        if name[0] == '#':
            log.msg( 'talking to channel %s %s %s '%
                     (self.nickname, prefix, params ))
            channame = name[1:]
            channel = self.factory.channels[channame]
            if channel in self.channels:
                channel.say(self, text)
        else:
            chatter = self.factory.chatters[name]
            chatter.hearWhisper(self, text)
        
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
        
    def lineReceived(self, line):
        prefix, command, params = parsemsg(line)
        # MIRC is a big pile of doo-doo
        command = string.upper(command)
        log.msg( "%s %s %s" % (prefix, command, params ))
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
        self.topic = 'Welcome to #%s' % name

    def say(self, user, message):
        for chatter in self.chatters:
            chatter.hearMsg(self, user, message)

class Evaluator(ChatRoom):
    nickname = "EvalServ"
    def say(self, user, message):
        value = eval(message)
        for chatter in self.chatters:
            chatter.hearMsg(self, self, "(%s) => (%s)" % (message, value))

class IRCFactory(protocol.Factory):
    def __init__(self):
        self.channels = {"eval":Evaluator("eval")}
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
