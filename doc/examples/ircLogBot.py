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

"""An example IRC log bot - logs a channel's events to a file."""


# twisted imports
from twisted.protocols import irc, protocol
from twisted.internet import main, app

# system imports
import string, time


class LogBot(irc.IRCClient):
    """A logging IRC bot."""
    def __init__(self):
        self.nickname = "twistedbot"

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)
        self.file = open(self.factory.filename, "a")
        self.log("[connected at %s]" % time.asctime(time.localtime(time.time())))

    def signedOn(self):
        self.join(self.factory.channel)

    def connectionLost(self):
        irc.IRCClient.connectionLost(self)
        self.log("[disconnected at %s]" % time.asctime(time.localtime(time.time())))
        self.file.close()

    def connectionFailed(self):
        irc.IRCClient.connectionFailed(self)
        self.file = open(self.factory.filename, "a")
        self.log("[connection failed at %s]" % time.asctime(time.localtime(time.time())))

    def log(self, s):
        timestamp = time.strftime("[%H:%M:%S]", time.localtime(time.time()))
        self.file.write("%s %s\n" % (timestamp, s))
        self.file.flush()

    

    # callbacks for events
    
    def joined(self, channel):
        self.log("[I have joined %s]" % channel)

    def privmsg(self, user, channel, msg):
        user = string.split(user, '!', 1)[0]
        self.log("<%s> %s" % (user, msg))

    def action(self, user, channel, msg):
        user = string.split(user, '!', 1)[0]
        self.log("* %s %s" % (user, msg))

    # irc callbacks
    
    def irc_NICK(self, prefix, params):
        """When an IRC user changes their nickname
        """
        old_nick = string.split(prefix,'!')[0]
        new_nick = params[0]
        self.log("%s is now known as %s" % (old_nick, new_nick))

    
class LogBotFactory(protocol.ClientFactory):
    """A factory for LogBots.

    A new protocol instance will be created each time we connect to the server.
    """

    # the class of the protocol to build
    protocol = LogBot
    
    def __init__(self, channel, filename):
        self.channel = channel
        self.filename = filename


if __name__ == '__main__':
    # create factory protocol and application
    import sys
    f = LogBotFactory(sys.argv[1], sys.argv[2])
    application = app.Application("logbot")

    # connect to this host and port, and reconnect if we get disconnected
    application.connectTCP("irc.openprojects.net", 6667, f)

    # run bot
    application.run(save=0)
