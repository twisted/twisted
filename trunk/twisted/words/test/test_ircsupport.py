# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.im.ircsupport}.
"""

from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransport

from twisted.words.im.basechat import Conversation, ChatUI
from twisted.words.im.ircsupport import IRCAccount, IRCProto



class StubConversation(Conversation):
    def show(self):
        pass



class StubChatUI(ChatUI):
    def getGroupConversation(self, group, Class=StubConversation, stayHidden=0):
        return ChatUI.getGroupConversation(self, group, Class, stayHidden)



class IRCProtoTests(TestCase):
    """
    Tests for L{IRCProto}.
    """
    def setUp(self):
        self.account = IRCAccount(
            "Some account", False, "alice", None, "example.com", 6667)
        self.proto = IRCProto(self.account, StubChatUI(), None)
        self.transport = StringTransport()


    def test_login(self):
        """
        When L{IRCProto} is connected to a transport, it sends I{NICK} and
        I{USER} commands with the username from the account object.
        """
        self.proto.makeConnection(self.transport)
        self.assertEqual(
            self.transport.value(),
            "NICK alice\r\n"
            "USER alice foo bar :Twisted-IM user\r\n")


    def test_authenticate(self):
        """
        If created with an account with a password, L{IRCProto} sends a
        I{PASS} command before the I{NICK} and I{USER} commands.
        """
        self.account.password = "secret"
        self.proto.makeConnection(self.transport)
        self.assertEqual(
            self.transport.value(),
            "PASS secret\r\n"
            "NICK alice\r\n"
            "USER alice foo bar :Twisted-IM user\r\n")


    def test_channels(self):
        """
        If created with an account with a list of channels, L{IRCProto}
        joins each of those channels after registering.
        """
        self.account.channels = ['#foo', '#bar']
        self.proto.makeConnection(self.transport)
        self.assertEqual(
            self.transport.value(),
            "NICK alice\r\n"
            "USER alice foo bar :Twisted-IM user\r\n"
            "JOIN #foo\r\n"
            "JOIN #bar\r\n")


    def test_isupport(self):
        """
        L{IRCProto} can interpret I{ISUPPORT} (I{005}) messages from the server
        and reflect their information in its C{supported} attribute.
        """
        self.proto.makeConnection(self.transport)
        self.proto.dataReceived(
            ":irc.example.com 005 alice MODES=4 CHANLIMIT=#:20\r\n")
        self.assertEqual(4, self.proto.supported.getFeature("MODES"))
