"""Internet Relay Chat Protocol implementation
"""

from twisted.protocols import basic
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
    trailing = None
    if x != -1:
        trailing = s[x+1:]
        s = s[:x]
    params = string.split(s, ' ')
    if trailing is not None:
        params.append(trailing)
    return prefix, command, params

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
