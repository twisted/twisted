
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

from twisted.words import service, tendril
from twisted.trial import unittest
from twisted.protocols import irc
from twisted.internet import protocol
import StringIO

tendril._LOGALL = 1

# Needs more tests!
#  irc join/part/quit
#  irc reconnection

class MessageCatcher:
    def receiveDirectMessage(self, sender, message):
        self.dmessages.append((sender.name, message))
        self.client.receiveDirectMessage(sender.name, message)

class GroupMessageCatcher:
    def sendMessage(self, sender, message):
        self.messages.append((sender.name, message))

class StringIOWithoutClosing(StringIO.StringIO):
    zeroAt = 0
    def close(self):
        pass

    def resetCounter(self):
        self.zeroAt = len(StringIO.StringIO.getvalue(self))

    def getvalue(self):
        return StringIO.StringIO.getvalue(self)[self.zeroAt:]

    def getAll(self):
        return StringIO.StringIO.getvalue(self)


class TendrilTest(unittest.TestCase):
    def setUp(self):
        self.service = service.Service("EAT IT FATTY")
        self.tendrilFactory = tendril.TendrilFactory(self.service)
        self.tendrilFactory.nickname = 'tl'
        self.tendrilFactory.groupList=['tendriltest']
        self.tendrilFactory.networkSuffix='@unittest'
        self.tendrilFactory.startFactory()
        self.file = StringIOWithoutClosing()
        self.transport = protocol.FileWrapper(self.file)
        self.transport.connected = 1
        self.tendril = self.tendrilFactory.buildProtocol(None)
        self.tendril.makeConnection(self.transport)

        self.tendril.signedOn()
        self.tendrilFactory.wordsclient.joinGroup('tendriltest')

        self.group = self.service.getGroup('tendriltest')
        self.participant = self.service.createParticipant('TheParticipant')
        self.participant.dmessages = []
        self.group.messages = []
        # ugh, this should be a bot or something, but it's easier this way
        self.participant.receiveDirectMessage = lambda sender, message, metadata=None, m=self.participant.dmessages: m.append((sender.perspectiveName, message))
        self.participant.receiveGroupMessage = lambda sender, group, message, metadata=None, m=self.group.messages: m.append((sender.perspectiveName, message))
        self.participant.joinGroup('tendriltest')


    def test_channelToGroup(self):
        """Testing IRC channel -> words.Group
        """
        s = ':ircDude!root@phreak.net PRIVMSG #TendrilTest :Whassup?'
        self.tendril.lineReceived(s)
        success = 0
        for sender, msg in self.group.messages:
            if (sender == 'ircDude@unittest') and (msg == "Whassup?"):
                success = 1

        self.failUnless(success, "none of these messages look right:\n%s"
                        % (self.group.messages,))


    def test_nickToParticipant(self):
        """Testing msg command -> Participant.directMessage
        """

        s = (":ircDude!root@phreak.net PRIVMSG %s "
             ":msg TheParticipant Whassup?"
             % (self.tendril.nickname,))

        self.tendril.lineReceived(s)
        success = 0
        for sender, msg in self.participant.dmessages:
            if (sender == 'ircDude@unittest') and (msg == "Whassup?"):
                success = 1

        self.failUnless(success, "none of these messages look right:\n%s"
                        % (self.group.messages,))


    def test_groupToChannel(self):
        """Testing words.Group -> IRC channel
        """

        expected_output = "PRIVMSG #tendriltest :<TheParticipant> Greetings!" + irc.CR + irc.LF

        self.file.resetCounter()
        self.participant.groupMessage('tendriltest', "Greetings!")
        output = self.file.getvalue()

        self.failUnlessEqual(expected_output, output)

    def test_participantToNick(self):
        """Testing words directMessage -> IRC user
        """

        expected_output = "PRIVMSG ircDude :<TheParticipant> Greetings!" + irc.CR + irc.LF

        s = ':ircDude!root@phreak.net PRIVMSG #TendrilTest :Whassup?'
        self.tendril.lineReceived(s)

        self.file.resetCounter()
        self.participant.directMessage('ircDude@unittest','Greetings!')
        output = self.file.getvalue()

        self.failUnlessEqual(expected_output, output)

if __name__ == '__main__':
    unittest.main()
