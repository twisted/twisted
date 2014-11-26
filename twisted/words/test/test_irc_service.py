# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for IRC portions of L{twisted.words.service}.
"""

from twisted.trial import unittest
from twisted.test import proto_helpers
from twisted.words.service import InMemoryWordsRealm, IRCFactory, IRCUser
from twisted.words.protocols import irc
from twisted.cred import checkers, portal

class IRCUserTests(unittest.TestCase):
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
        self.assertEqual(":example.com foo mynick\r\n",
                          self.stringTransport.value())


    def test_utf8Messages(self):
        """
        When a UTF8 message is sent with sendMessage and the current IRCUser
        has a UTF8 nick and is set to UTF8 encoding, the message will be
        written to the transport.
        """
        expectedResult = (u":example.com \u0442\u0435\u0441\u0442 "
                          u"\u043d\u0438\u043a\r\n").encode('utf-8')

        self.ircUser.irc_NICK("", [u"\u043d\u0438\u043a".encode('utf-8')])
        self.stringTransport.clear()
        self.ircUser.sendMessage(u"\u0442\u0435\u0441\u0442".encode('utf-8'))
        self.assertEqual(self.stringTransport.value(), expectedResult)


    def test_invalidEncodingNick(self):
        """
        A NICK command sent with a nickname that cannot be decoded with the
        current IRCUser's encoding results in a PRIVMSG from NickServ
        indicating that the nickname could not be decoded.
        """
        expectedResult = (b":NickServ!NickServ@services PRIVMSG "
                          b"\xd4\xc5\xd3\xd4 :Your nickname cannot be "
                          b"decoded. Please use ASCII or UTF-8.\r\n")

        self.ircUser.irc_NICK("", [b"\xd4\xc5\xd3\xd4"])
        self.assertEqual(self.stringTransport.value(), expectedResult)


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
        by L{IRCUserTests.response}

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
        self.assertEqual(start,
            [(0, ('example.com', '375', ['mynick', '- example.com Message of the Day - ']))])
        self.assertEqual(end,
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

        self.assertEqual(self.response(),
            [('example.com', '375',
              ['john', '- example.com Message of the Day - ']),
             ('example.com', '376', ['john', 'End of /MOTD command.']),
             ('example.com', '001', ['john', 'connected to Twisted IRC']),
             ('example.com', '002', ['john', version]),
             ('example.com', '003', ['john', creation]),
             ('example.com', '004',
              ['john', 'example.com', self.factory._serverInfo["serviceVersion"],
               'w', 'n'])])



class MocksyIRCUser(IRCUser):
    def __init__(self):
        self.mockedCodes = []

    def sendMessage(self, code, *_, **__):
        self.mockedCodes.append(code)

BADTEXT = '\xff'

class IRCUserBadEncodingTests(unittest.TestCase):
    """
    Verifies that L{IRCUser} sends the correct error messages back to clients
    when given indecipherable bytes
    """
    # TODO: irc_NICK -- but NICKSERV is used for that, so it isn't as easy.

    def setUp(self):
        self.ircuser = MocksyIRCUser()

    def assertChokesOnBadBytes(self, irc_x, error):
        """
        Asserts that IRCUser sends the relevant error code when a given irc_x
        dispatch method is given undecodable bytes.

        @param irc_x: the name of the irc_FOO method to test.
        For example, irc_x = 'PRIVMSG' will check irc_PRIVMSG

        @param error: the error code irc_x should send. For example,
        irc.ERR_NOTONCHANNEL
        """
        getattr(self.ircuser, 'irc_%s' % irc_x)(None, [BADTEXT])
        self.assertEqual(self.ircuser.mockedCodes, [error])

    # no such channel

    def test_JOIN(self):
        """
        Tests that irc_JOIN sends ERR_NOSUCHCHANNEL if the channel name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('JOIN', irc.ERR_NOSUCHCHANNEL)

    def test_NAMES(self):
        """
        Tests that irc_NAMES sends ERR_NOSUCHCHANNEL if the channel name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('NAMES', irc.ERR_NOSUCHCHANNEL)

    def test_TOPIC(self):
        """
        Tests that irc_TOPIC sends ERR_NOSUCHCHANNEL if the channel name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('TOPIC', irc.ERR_NOSUCHCHANNEL)

    def test_LIST(self):
        """
        Tests that irc_LIST sends ERR_NOSUCHCHANNEL if the channel name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('LIST', irc.ERR_NOSUCHCHANNEL)

    # no such nick

    def test_MODE(self):
        """
        Tests that irc_MODE sends ERR_NOSUCHNICK if the target name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('MODE', irc.ERR_NOSUCHNICK)

    def test_PRIVMSG(self):
        """
        Tests that irc_PRIVMSG sends ERR_NOSUCHNICK if the target name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('PRIVMSG', irc.ERR_NOSUCHNICK)

    def test_WHOIS(self):
        """
        Tests that irc_WHOIS sends ERR_NOSUCHNICK if the target name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('WHOIS', irc.ERR_NOSUCHNICK)

    # not on channel

    def test_PART(self):
        """
        Tests that irc_PART sends ERR_NOTONCHANNEL if the target name can't
        be decoded.
        """
        self.assertChokesOnBadBytes('PART', irc.ERR_NOTONCHANNEL)

    # probably nothing

    def test_WHO(self):
        """
        Tests that irc_WHO immediately ends the WHO list if the target name
        can't be decoded.
        """
        self.assertChokesOnBadBytes('WHO', irc.RPL_ENDOFWHO)
