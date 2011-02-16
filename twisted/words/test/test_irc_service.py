# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for IRC portions of L{twisted.words.service}.
"""

from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.words.service import InMemoryWordsRealm, IRCFactory
from twisted.words.protocols import irc
from twisted.cred import checkers, portal

class IRCUserTestCase(unittest.TestCase):
    """
    Isolated tests for L{IRCUser}
    """

    def setUp(self):
        """
        Sets up a Realm, Portal, Factory, IRCUser, Transport, and Connection
        for our tests.
        """
        self.wordsRealm = InMemoryWordsRealm("example.com")
        self.portal = portal.Portal(self.wordsRealm,
            [checkers.InMemoryUsernamePasswordDatabaseDontUse(john="pass")])
        self.factory = IRCFactory(self.wordsRealm, self.portal)
        self.ircUser = self.factory.buildProtocol(None)
        self.stringTransport = proto_helpers.StringTransport()
        self.ircUser.makeConnection(self.stringTransport)


    def test_sendMessage(self):
        """
        Sending a message to a user after they have sent NICK, but before they
        have authenticated, results in a message from "example.com".
        """
        self.ircUser.irc_NICK("", ["mynick"])
        self.stringTransport.clear()
        self.ircUser.sendMessage("foo")
        self.assertEquals(":example.com foo mynick\r\n",
                          self.stringTransport.value())


    def response(self):
        """
        Grabs our responses and then clears the transport
        """
        response = self.ircUser.transport.value().splitlines()
        self.ircUser.transport.clear()
        return map(irc.parsemsg, response)


    def scanResponse(self, response, messageType):
        """
        Gets messages out of a response
        
        @param response: The parsed IRC messages of the response, as returned
        by L{IRCServiceTestCase.response}
        
        @param messageType: The string type of the desired messages.
        
        @return: An iterator which yields 2-tuples of C{(index, ircMessage)}
        """
        for n, message in enumerate(response):
            if (message[1] == messageType):
                yield n, message


    def test_sendNickSendsGreeting(self):
        """
        Receiving NICK without authenticating sends the MOTD Start and MOTD End
        messages, which is required by certain popular IRC clients (such as
        Pidgin) before a connection is considered to be fully established.
        """
        self.ircUser.irc_NICK("", ["mynick"])
        response = self.response()
        start = list(self.scanResponse(response, irc.RPL_MOTDSTART))
        end = list(self.scanResponse(response, irc.RPL_ENDOFMOTD))
        self.assertEquals(start,
            [(0, ('example.com', '375', ['mynick', '- example.com Message of the Day - ']))])
        self.assertEquals(end,
            [(1, ('example.com', '376', ['mynick', 'End of /MOTD command.']))])


    def test_fullLogin(self):
        """
        Receiving USER, PASS, NICK will log in the user, and transmit the
        appropriate response messages.
        """
        self.ircUser.irc_USER("", ["john doe"])
        self.ircUser.irc_PASS("", ["pass"])
        self.ircUser.irc_NICK("", ["john"])

        version = ('Your host is example.com, running version %s' %
            (self.factory._serverInfo["serviceVersion"],))

        creation = ('This server was created on %s' %
            (self.factory._serverInfo["creationDate"],))

        self.assertEquals(self.response(),
            [('example.com', '375',
              ['john', '- example.com Message of the Day - ']),
             ('example.com', '376', ['john', 'End of /MOTD command.']),
             ('example.com', '001', ['john', 'connected to Twisted IRC']),
             ('example.com', '002', ['john', version]),
             ('example.com', '003', ['john', creation]),
             ('example.com', '004',
              ['john', 'example.com', self.factory._serverInfo["serviceVersion"],
               'w', 'n'])])
