
from twisted.protocols.irc import IRC
from twisted.python import log
from twisted.protocols.protocol import Factory

class IRCUserInterface(IRC):
    def connectionLost(self):
        del self.factory.ircui

class IRCUIFactory(Factory):
    ircui = None
    def buildProtocol(self):
        if self.ircui:
            log.msg("already logged in")
            return None
        i = IRCUserInterface()
        i.factory = self
        self.ircui = i
        return i

