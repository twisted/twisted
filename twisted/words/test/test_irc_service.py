# Copyright (c) 2009 Twisted Matrix Laboratories.
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
        self.hostname = 'example.com'
        self.wordsRealm = InMemoryWordsRealm(self.hostname)
        self.portal = portal.Portal(self.wordsRealm,
            [checkers.InMemoryUsernamePasswordDatabaseDontUse(
                john="pass",
                jane="pass")])
        self.factory = IRCFactory(self.wordsRealm, self.portal)

        self.ircUser = self.factory.buildProtocol(None)
        self.stringTransport = proto_helpers.StringTransport()
        self.ircUser.makeConnection(self.stringTransport)

        self.ircUser2 = self.factory.buildProtocol(None)
        self.stringTransport2 = proto_helpers.StringTransport()
        self.ircUser2.makeConnection(self.stringTransport2)


    def test_sendMessage(self):
        """
        Sending a message to a user after they have sent NICK, but before they
        have authenticated, results in a message from "example.com".
        """
        self.ircUser.irc_NICK("", ["mynick"])
        self.stringTransport.clear()
        self.ircUser.sendMessage("foo")
        self.assertEquals(":%s foo mynick\r\n" % (self.hostname,),
                          self.stringTransport.value())


    def response(self, ircUser):
        """
        Grabs our responses and then clears the transport
        """
        response = ircUser.transport.value().splitlines()
        ircUser.transport.clear()
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
        response = self.response(self.ircUser)
        start = list(self.scanResponse(response, irc.RPL_MOTDSTART))
        end = list(self.scanResponse(response, irc.RPL_ENDOFMOTD))
        self.assertEquals(start,
            [(0, (self.hostname, '375', ['mynick', '- example.com Message of the Day - ']))])
        self.assertEquals(end,
            [(1, (self.hostname, '376', ['mynick', 'End of /MOTD command.']))])


    def test_fullLogin(self):
        """
        Receiving USER, PASS, NICK will log in the user, and transmit the
        appropriate response messages.
        """
        self.ircUser.irc_USER("", ["john doe"])
        self.ircUser.irc_PASS("", ["pass"])
        self.ircUser.irc_NICK("", ["john"])

        version = ('Your host is %s, running version %s' %
            (self.hostname, self.factory._serverInfo["serviceVersion"],))

        creation = ('This server was created on %s' %
            (self.factory._serverInfo["creationDate"],))

        self.assertEquals(self.response(self.ircUser),
            [(self.hostname, '375',
              ['john', '- example.com Message of the Day - ']),
             (self.hostname, '376', ['john', 'End of /MOTD command.']),
             (self.hostname, '001', ['john', 'connected to Twisted IRC']),
             (self.hostname, '002', ['john', version]),
             (self.hostname, '003', ['john', creation]),
             (self.hostname, '004',
              ['john', self.hostname, self.factory._serverInfo["serviceVersion"],
               'w', 'n'])])


    def test_awayMessage(self):
        """
        Receiving AWAY <msg> should put the user into the AWAY state.  PRIVMSG
        commands directed at that user should not be delivered; instead, a
        RPL_AWAY response with the message should be returned. Also check for
        RPL_NOWAWAY and RPL_UNAWAY responses to the AWAY command.
        """

        # First, login both clients
        self.ircUser.irc_USER('', ['john doe'])
        self.ircUser.irc_PASS('', ['pass'])
        self.ircUser.irc_NICK('', ['john'])
        self.response(self.ircUser) # just dump these responses

        self.ircUser2.irc_USER('', ['jane doe'])
        self.ircUser2.irc_PASS('', ['pass'])
        self.ircUser2.irc_NICK('', ['jane'])
        self.response(self.ircUser2) # just dump these responses

        # user2 tries to msg user1
        self.ircUser2.irc_PRIVMSG('', ['john', 'Are you there?'])
        self.assertEquals(self.response(self.ircUser2), [])

        # user1 gets the message
        self.assertEquals(self.response(self.ircUser),
            [('jane!jane@%s' % (self.hostname,), 'PRIVMSG',
                ['john', 'Are you there?'])])

        # set user1 away
        self.ircUser.irc_AWAY('', ['I am away.'])
        self.assertEquals(self.response(self.ircUser),
            [(self.hostname, irc.RPL_NOWAWAY,
                ['john', 'You have been marked as being away'])])

        # user2 tries to msg user1
        self.ircUser2.irc_PRIVMSG('', ['john', 'Are you there?'])
        self.assertEquals(self.response(self.ircUser2),
            [(self.hostname, irc.RPL_AWAY,
                ['jane', 'I am away.'])])

        # user1 comes back
        self.ircUser.irc_AWAY('', [])
        self.assertEquals(self.response(self.ircUser),
            [(self.hostname, irc.RPL_UNAWAY,
                ['john', 'You are no longer marked as being away'])])

        # user2 tries to msg user1
        self.ircUser2.irc_PRIVMSG('', ['john', 'Are you there?'])
        self.assertEquals(self.response(self.ircUser2), [])

        # user1 gets the message
        self.assertEquals(self.response(self.ircUser),
            [('jane!jane@%s' % (self.hostname,), 'PRIVMSG',
                ['john', 'Are you there?'])])
