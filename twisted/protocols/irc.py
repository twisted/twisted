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
        self.buffer = self.buffer + data
        lines = string.split(self.buffer, "\n") # get the lines
        self.buffer = lines.pop() # pop the last element (we're not sure it's a line)
        for line in lines:
            if line[-1] == "\r":
                line = line[:-1]
            prefix, command, params = parsemsg(line)
            # MIRC is a big pile of doo-doo
            command = string.upper(command)
            log.msg( "%s %s %s" % (prefix, command, params))
            method = getattr(self, "irc_%s" % command, None)
            if method is not None:
                method(prefix, params)
            else:
                self.irc_unknown(prefix, command, params)

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
