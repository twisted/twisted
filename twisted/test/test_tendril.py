
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
from pyunit import unittest
from twisted.protocols import irc
from twisted.internet import protocol
import StringIO

tendril._LOGALL = 0

class NoOpper:
    def __getattr__(self, key):
        return self

    def __call__(self, *a, **kw):
        return self

class DummyPerspective:
    def __init__(self, name, service):
        self.name = name
        self.service = service
        self.client = NoOpper()
        self.dmessages = []

    def receiveGroupMessage(self, sender, group, message):
        self.client.receiveGroupMessage(sender.name, group.name, message)

    def receiveDirectMessage(self, sender, message):
        self.dmessages.append((sender.name, message))
        self.client.receiveDirectMessage(sender.name, message)

    def directMessage(self, recipientName, message):
        recipient = self.service.getPerspectiveNamed(recipientName)
        recipient.receiveDirectMessage(self, message)

    def groupMessage(self, groupName, message):
        group = self.service.getGroup(groupName)
        group.sendMessage(self, message)

    def attached(self, client, identity=None):
        self.client = client

    def detached(self, *unused):
        pass

    def joinGroup(self, groupName):
        group = self.service.getGroup(groupName)
        group.addMember(self)

    def __str__(self):
        return "<participant '%s' at %x>" % (self.name, id(self))

class DummyGroup:
    def __init__(self, name):
        self.name = name
        self.members = []
        self.messages = []

    def addMember(self, member):
        self.members.append(member)

    def sendMessage(self, sender, message):
        if self.name == 'TendrilErrors':
            pass
        self.messages.append((sender.name, message))
        for member in self.members:
            member.receiveGroupMessage(sender, self, message)


class DummyService:
    def __init__(self, name):
        self.serviceName = name
        self.perspectives = {}
        self.groups = {}

    def getGroup(self, name):
        group = self.groups.get(name)
        if not group:
            group = DummyGroup(name)
            self.groups[name] = group
        return group

    def getPerspectiveNamed(self, name):
        try:
            p = self.perspectives[name]
        except KeyError:
            raise service.UserNonexistantError(name)
        else:
            return p

    def createParticipant(self, name):
        self.perspectives[name] = DummyPerspective(name, self)
        return self.perspectives[name]

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
        self.service = DummyService("twisted.words.TendrilTest")
        self.tendril = tendril.TendrilClient(
            self.service, groupList=['tendriltest'],
            networkSuffix='@unittest')
        self.file = StringIOWithoutClosing()
        self.transport = protocol.FileWrapper(self.file)
        self.transport.connected = 1
        self.tendril.makeConnection(self.transport)

        self.tendril.signedOn()
        self.tendril.joinGroup('tendriltest')

        self.group = self.service.getGroup('tendriltest')
        self.participant = self.service.createParticipant('TheParticipant')
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
