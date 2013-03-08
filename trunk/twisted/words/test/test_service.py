# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.words.service}.
"""

import time

from twisted.trial import unittest
from twisted.test import proto_helpers

from twisted.cred import portal, credentials, checkers
from twisted.words import ewords, service
from twisted.words.protocols import irc
from twisted.spread import pb
from twisted.internet.defer import Deferred, DeferredList, maybeDeferred, succeed
from twisted.internet.defer import deferredGenerator as dG, waitForDeferred as wFD
from twisted.internet import address, reactor

class RealmTestCase(unittest.TestCase):
    def _entityCreationTest(self, kind):
        # Kind is "user" or "group"
        realm = service.InMemoryWordsRealm("realmname")

        name = u'test' + kind.lower()
        create = getattr(realm, 'create' + kind.title())
        get = getattr(realm, 'get' + kind.title())
        flag = 'create' + kind.title() + 'OnRequest'
        dupExc = getattr(ewords, 'Duplicate' + kind.title())
        noSuchExc = getattr(ewords, 'NoSuch' + kind.title())

        # Creating should succeed
        d = wFD(create(name))
        yield d
        p = d.getResult()
        self.assertEqual(p.name, name)

        # Creating the same user again should not
        d = wFD(create(name))
        yield d
        self.assertRaises(dupExc, d.getResult)

        # Getting a non-existent user should succeed if createUserOnRequest is True
        setattr(realm, flag, True)
        d = wFD(get(u"new" + kind.lower()))
        yield d
        p = d.getResult()
        self.assertEqual(p.name, "new" + kind.lower())

        # Getting that user again should return the same object
        d = wFD(get(u"new" + kind.lower()))
        yield d
        newp = d.getResult()
        self.assertIdentical(p, newp)

        # Getting a non-existent user should fail if createUserOnRequest is False
        setattr(realm, flag, False)
        d = wFD(get(u"another" + kind.lower()))
        yield d
        self.assertRaises(noSuchExc, d.getResult)
    _entityCreationTest = dG(_entityCreationTest)


    def testUserCreation(self):
        return self._entityCreationTest("User")


    def testGroupCreation(self):
        return self._entityCreationTest("Group")


    def testUserRetrieval(self):
        realm = service.InMemoryWordsRealm("realmname")

        # Make a user to play around with
        d = wFD(realm.createUser(u"testuser"))
        yield d
        user = d.getResult()

        # Make sure getting the user returns the same object
        d = wFD(realm.getUser(u"testuser"))
        yield d
        retrieved = d.getResult()
        self.assertIdentical(user, retrieved)

        # Make sure looking up the user also returns the same object
        d = wFD(realm.lookupUser(u"testuser"))
        yield d
        lookedUp = d.getResult()
        self.assertIdentical(retrieved, lookedUp)

        # Make sure looking up a user who does not exist fails
        d = wFD(realm.lookupUser(u"nosuchuser"))
        yield d
        self.assertRaises(ewords.NoSuchUser, d.getResult)
    testUserRetrieval = dG(testUserRetrieval)


    def testUserAddition(self):
        realm = service.InMemoryWordsRealm("realmname")

        # Create and manually add a user to the realm
        p = service.User("testuser")
        d = wFD(realm.addUser(p))
        yield d
        user = d.getResult()
        self.assertIdentical(p, user)

        # Make sure getting that user returns the same object
        d = wFD(realm.getUser(u"testuser"))
        yield d
        retrieved = d.getResult()
        self.assertIdentical(user, retrieved)

        # Make sure looking up that user returns the same object
        d = wFD(realm.lookupUser(u"testuser"))
        yield d
        lookedUp = d.getResult()
        self.assertIdentical(retrieved, lookedUp)
    testUserAddition = dG(testUserAddition)


    def testGroupRetrieval(self):
        realm = service.InMemoryWordsRealm("realmname")

        d = wFD(realm.createGroup(u"testgroup"))
        yield d
        group = d.getResult()

        d = wFD(realm.getGroup(u"testgroup"))
        yield d
        retrieved = d.getResult()

        self.assertIdentical(group, retrieved)

        d = wFD(realm.getGroup(u"nosuchgroup"))
        yield d
        self.assertRaises(ewords.NoSuchGroup, d.getResult)
    testGroupRetrieval = dG(testGroupRetrieval)


    def testGroupAddition(self):
        realm = service.InMemoryWordsRealm("realmname")

        p = service.Group("testgroup")
        d = wFD(realm.addGroup(p))
        yield d
        d.getResult()

        d = wFD(realm.getGroup(u"testGroup"))
        yield d
        group = d.getResult()

        self.assertIdentical(p, group)
    testGroupAddition = dG(testGroupAddition)


    def testGroupUsernameCollision(self):
        """
        Try creating a group with the same name as an existing user and
        assert that it succeeds, since users and groups should not be in the
        same namespace and collisions should be impossible.
        """
        realm = service.InMemoryWordsRealm("realmname")

        d = wFD(realm.createUser(u"test"))
        yield d
        user = d.getResult()

        d = wFD(realm.createGroup(u"test"))
        yield d
        group = d.getResult()
    testGroupUsernameCollision = dG(testGroupUsernameCollision)


    def testEnumeration(self):
        realm = service.InMemoryWordsRealm("realmname")
        d = wFD(realm.createGroup(u"groupone"))
        yield d
        d.getResult()

        d = wFD(realm.createGroup(u"grouptwo"))
        yield d
        d.getResult()

        groups = wFD(realm.itergroups())
        yield groups
        groups = groups.getResult()

        n = [g.name for g in groups]
        n.sort()
        self.assertEqual(n, ["groupone", "grouptwo"])
    testEnumeration = dG(testEnumeration)


class TestGroup(object):
    def __init__(self, name, size, topic):
        self.name = name
        self.size = lambda: size
        self.meta = {'topic': topic}


class TestUser(object):
    def __init__(self, name, groups, signOn, lastMessage):
        self.name = name
        self.itergroups = lambda: iter([TestGroup(g, 3, 'Hello') for g in groups])
        self.signOn = signOn
        self.lastMessage = lastMessage


class TestPortal(object):
    def __init__(self):
        self.logins = []


    def login(self, credentials, mind, *interfaces):
        d = Deferred()
        self.logins.append((credentials, mind, interfaces, d))
        return d


class TestCaseUserAgg(object):
    def __init__(self, user, realm, factory, address=address.IPv4Address('TCP', '127.0.0.1', 54321)):
        self.user = user
        self.transport = proto_helpers.StringTransportWithDisconnection()
        self.protocol = factory.buildProtocol(address)
        self.transport.protocol = self.protocol
        self.user.mind = self.protocol
        self.protocol.makeConnection(self.transport)


    def write(self, stuff):
        if isinstance(stuff, unicode):
            stuff = stuff.encode('utf-8')
        self.protocol.dataReceived(stuff)


class IRCProtocolTestCase(unittest.TestCase):
    STATIC_USERS = [
        u'useruser', u'otheruser', u'someguy', u'firstuser', u'username',
        u'userone', u'usertwo', u'userthree', u'someuser']


    def setUp(self):
        self.realm = service.InMemoryWordsRealm("realmname")
        self.checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        self.portal = portal.Portal(self.realm, [self.checker])
        self.factory = service.IRCFactory(self.realm, self.portal)

        c = []
        for nick in self.STATIC_USERS:
            c.append(self.realm.createUser(nick))
            self.checker.addUser(nick.encode('ascii'), nick + "_password")
        return DeferredList(c)


    def _assertGreeting(self, user):
        """
        The user has been greeted with the four messages that are (usually)
        considered to start an IRC session.
        
        Asserts that the required responses were received.
        """
        # Make sure we get 1-4 at least
        response = self._response(user)
        expected = [irc.RPL_WELCOME, irc.RPL_YOURHOST, irc.RPL_CREATED,
                    irc.RPL_MYINFO]
        for (prefix, command, args) in response:
            if command in expected:
                expected.remove(command)
        self.failIf(expected, "Missing responses for %r" % (expected,))


    def _login(self, user, nick, password=None):
        if password is None:
            password = nick + "_password"
        user.write('PASS %s\r\n' % (password,))
        user.write('NICK %s extrainfo\r\n' % (nick,))


    def _loggedInUser(self, name):
        d = wFD(self.realm.lookupUser(name))
        yield d
        user = d.getResult()
        agg = TestCaseUserAgg(user, self.realm, self.factory)
        self._login(agg, name)
        yield agg
    _loggedInUser = dG(_loggedInUser)


    def _response(self, user, messageType=None):
        """
        Extracts the user's response, and returns a list of parsed lines.
        If messageType is defined, only messages of that type will be returned.
        """
        response = user.transport.value().splitlines()
        user.transport.clear()
        result = []
        for message in map(irc.parsemsg, response):
            if messageType is None or message[1] == messageType:
                result.append(message)
        return result


    def testPASSLogin(self):
        user = wFD(self._loggedInUser(u'firstuser'))
        yield user
        user = user.getResult()
        self._assertGreeting(user)
    testPASSLogin = dG(testPASSLogin)


    def test_nickServLogin(self):
        """
        Sending NICK without PASS will prompt the user for their password.
        When the user sends their password to NickServ, it will respond with a
        Greeting.
        """
        firstuser = wFD(self.realm.lookupUser(u'firstuser'))
        yield firstuser
        firstuser = firstuser.getResult()

        user = TestCaseUserAgg(firstuser, self.realm, self.factory)
        user.write('NICK firstuser extrainfo\r\n')
        response = self._response(user, 'PRIVMSG')
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][0], service.NICKSERV)
        self.assertEqual(response[0][1], 'PRIVMSG')
        self.assertEqual(response[0][2], ['firstuser', 'Password?'])
        user.transport.clear()

        user.write('PRIVMSG nickserv firstuser_password\r\n')
        self._assertGreeting(user)
    test_nickServLogin = dG(test_nickServLogin)


    def testFailedLogin(self):
        firstuser = wFD(self.realm.lookupUser(u'firstuser'))
        yield firstuser
        firstuser = firstuser.getResult()

        user = TestCaseUserAgg(firstuser, self.realm, self.factory)
        self._login(user, "firstuser", "wrongpass")
        response = self._response(user, "PRIVMSG")
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][2], ['firstuser', 'Login failed.  Goodbye.'])
    testFailedLogin = dG(testFailedLogin)


    def testLogout(self):
        logout = []
        firstuser = wFD(self.realm.lookupUser(u'firstuser'))
        yield firstuser
        firstuser = firstuser.getResult()

        user = TestCaseUserAgg(firstuser, self.realm, self.factory)
        self._login(user, "firstuser")
        user.protocol.logout = lambda: logout.append(True)
        user.write('QUIT\r\n')
        self.assertEqual(logout, [True])
    testLogout = dG(testLogout)


    def testJoin(self):
        firstuser = wFD(self.realm.lookupUser(u'firstuser'))
        yield firstuser
        firstuser = firstuser.getResult()

        somechannel = wFD(self.realm.createGroup(u"somechannel"))
        yield somechannel
        somechannel = somechannel.getResult()

        somechannel.meta['topic'] = 'some random topic'

        # Bring in one user, make sure he gets into the channel sanely
        user = TestCaseUserAgg(firstuser, self.realm, self.factory)
        self._login(user, "firstuser")
        user.transport.clear()
        user.write('JOIN #somechannel\r\n')

        response = self._response(user)
        self.assertEqual(len(response), 5)

        # Join message
        self.assertEqual(response[0][0], 'firstuser!firstuser@realmname')
        self.assertEqual(response[0][1], 'JOIN')
        self.assertEqual(response[0][2], ['#somechannel'])

        # User list
        self.assertEqual(response[1][1], '353')
        self.assertEqual(response[2][1], '366')

        # Topic (or lack thereof, as the case may be)
        self.assertEqual(response[3][1], '332')
        self.assertEqual(response[4][1], '333')


        # Hook up another client!  It is a CHAT SYSTEM!!!!!!!
        other = wFD(self._loggedInUser(u'otheruser'))
        yield other
        other = other.getResult()

        other.transport.clear()
        user.transport.clear()
        other.write('JOIN #somechannel\r\n')

        # At this point, both users should be in the channel
        response = self._response(other)

        event = self._response(user)
        self.assertEqual(len(event), 1)
        self.assertEqual(event[0][0], 'otheruser!otheruser@realmname')
        self.assertEqual(event[0][1], 'JOIN')
        self.assertEqual(event[0][2], ['#somechannel'])

        self.assertEqual(response[1][0], 'realmname')
        self.assertEqual(response[1][1], '353')
        self.assertIn(response[1][2], [
                      ['otheruser', '=', '#somechannel', 'firstuser otheruser'],
                      ['otheruser', '=', '#somechannel', 'otheruser firstuser'],
                      ])
    testJoin = dG(testJoin)


    def test_joinTopicless(self):
        """
        When a user joins a group without a topic, no topic information is
        sent to that user.
        """
        firstuser = wFD(self.realm.lookupUser(u'firstuser'))
        yield firstuser
        firstuser = firstuser.getResult()

        somechannel = wFD(self.realm.createGroup(u"somechannel"))
        yield somechannel
        somechannel = somechannel.getResult()

        # Bring in one user, make sure he gets into the channel sanely
        user = TestCaseUserAgg(firstuser, self.realm, self.factory)
        self._login(user, "firstuser")
        user.transport.clear()
        user.write('JOIN #somechannel\r\n')

        response = self._response(user)
        responseCodes = [r[1] for r in response]
        self.assertNotIn('332', responseCodes)
        self.assertNotIn('333', responseCodes)
    test_joinTopicless = dG(test_joinTopicless)


    def testLeave(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        somechannel = wFD(self.realm.createGroup(u"somechannel"))
        yield somechannel
        somechannel = somechannel.getResult()

        user.write('JOIN #somechannel\r\n')
        user.transport.clear()

        other = wFD(self._loggedInUser(u'otheruser'))
        yield other
        other = other.getResult()

        other.write('JOIN #somechannel\r\n')

        user.transport.clear()
        other.transport.clear()

        user.write('PART #somechannel\r\n')

        response = self._response(user)
        event = self._response(other)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][0], 'useruser!useruser@realmname')
        self.assertEqual(response[0][1], 'PART')
        self.assertEqual(response[0][2], ['#somechannel', 'leaving'])
        self.assertEqual(response, event)

        # Now again, with a part message
        user.write('JOIN #somechannel\r\n')

        user.transport.clear()
        other.transport.clear()

        user.write('PART #somechannel :goodbye stupidheads\r\n')

        response = self._response(user)
        event = self._response(other)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][0], 'useruser!useruser@realmname')
        self.assertEqual(response[0][1], 'PART')
        self.assertEqual(response[0][2], ['#somechannel', 'goodbye stupidheads'])
        self.assertEqual(response, event)
    testLeave = dG(testLeave)


    def testGetTopic(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        group = service.Group("somechannel")
        group.meta["topic"] = "This is a test topic."
        group.meta["topic_author"] = "some_fellow"
        group.meta["topic_date"] = 77777777

        add = wFD(self.realm.addGroup(group))
        yield add
        add.getResult()

        user.transport.clear()
        user.write("JOIN #somechannel\r\n")

        response = self._response(user)

        self.assertEqual(response[3][0], 'realmname')
        self.assertEqual(response[3][1], '332')

        # XXX Sigh.  irc.parsemsg() is not as correct as one might hope.
        self.assertEqual(response[3][2], ['useruser', '#somechannel', 'This is a test topic.'])
        self.assertEqual(response[4][1], '333')
        self.assertEqual(response[4][2], ['useruser', '#somechannel', 'some_fellow', '77777777'])

        user.transport.clear()

        user.write('TOPIC #somechannel\r\n')

        response = self._response(user)

        self.assertEqual(response[0][1], '332')
        self.assertEqual(response[0][2], ['useruser', '#somechannel', 'This is a test topic.'])
        self.assertEqual(response[1][1], '333')
        self.assertEqual(response[1][2], ['useruser', '#somechannel', 'some_fellow', '77777777'])
    testGetTopic = dG(testGetTopic)


    def testSetTopic(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        add = wFD(self.realm.createGroup(u"somechannel"))
        yield add
        somechannel = add.getResult()

        user.write("JOIN #somechannel\r\n")

        other = wFD(self._loggedInUser(u'otheruser'))
        yield other
        other = other.getResult()

        other.write("JOIN #somechannel\r\n")

        user.transport.clear()
        other.transport.clear()

        other.write('TOPIC #somechannel :This is the new topic.\r\n')

        response = self._response(other)
        event = self._response(user)

        self.assertEqual(response, event)

        self.assertEqual(response[0][0], 'otheruser!otheruser@realmname')
        self.assertEqual(response[0][1], 'TOPIC')
        self.assertEqual(response[0][2], ['#somechannel', 'This is the new topic.'])

        other.transport.clear()

        somechannel.meta['topic_date'] = 12345
        other.write('TOPIC #somechannel\r\n')

        response = self._response(other)
        self.assertEqual(response[0][1], '332')
        self.assertEqual(response[0][2], ['otheruser', '#somechannel', 'This is the new topic.'])
        self.assertEqual(response[1][1], '333')
        self.assertEqual(response[1][2], ['otheruser', '#somechannel', 'otheruser', '12345'])

        other.transport.clear()
        other.write('TOPIC #asdlkjasd\r\n')

        response = self._response(other)
        self.assertEqual(response[0][1], '403')
    testSetTopic = dG(testSetTopic)


    def testGroupMessage(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        add = wFD(self.realm.createGroup(u"somechannel"))
        yield add
        somechannel = add.getResult()

        user.write("JOIN #somechannel\r\n")

        other = wFD(self._loggedInUser(u'otheruser'))
        yield other
        other = other.getResult()

        other.write("JOIN #somechannel\r\n")

        user.transport.clear()
        other.transport.clear()

        user.write('PRIVMSG #somechannel :Hello, world.\r\n')

        response = self._response(user)
        event = self._response(other)

        self.failIf(response)
        self.assertEqual(len(event), 1)
        self.assertEqual(event[0][0], 'useruser!useruser@realmname')
        self.assertEqual(event[0][1], 'PRIVMSG', -1)
        self.assertEqual(event[0][2], ['#somechannel', 'Hello, world.'])
    testGroupMessage = dG(testGroupMessage)


    def testPrivateMessage(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        other = wFD(self._loggedInUser(u'otheruser'))
        yield other
        other = other.getResult()

        user.transport.clear()
        other.transport.clear()

        user.write('PRIVMSG otheruser :Hello, monkey.\r\n')

        response = self._response(user)
        event = self._response(other)

        self.failIf(response)
        self.assertEqual(len(event), 1)
        self.assertEqual(event[0][0], 'useruser!useruser@realmname')
        self.assertEqual(event[0][1], 'PRIVMSG')
        self.assertEqual(event[0][2], ['otheruser', 'Hello, monkey.'])

        user.write('PRIVMSG nousernamedthis :Hello, monkey.\r\n')

        response = self._response(user)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][0], 'realmname')
        self.assertEqual(response[0][1], '401')
        self.assertEqual(response[0][2], ['useruser', 'nousernamedthis', 'No such nick/channel.'])
    testPrivateMessage = dG(testPrivateMessage)


    def testOper(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        user.transport.clear()
        user.write('OPER user pass\r\n')
        response = self._response(user)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][1], '491')
    testOper = dG(testOper)


    def testGetUserMode(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        user.transport.clear()
        user.write('MODE useruser\r\n')

        response = self._response(user)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][0], 'realmname')
        self.assertEqual(response[0][1], '221')
        self.assertEqual(response[0][2], ['useruser', '+'])
    testGetUserMode = dG(testGetUserMode)


    def testSetUserMode(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        user.transport.clear()
        user.write('MODE useruser +abcd\r\n')

        response = self._response(user)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][1], '472')
    testSetUserMode = dG(testSetUserMode)


    def testGetGroupMode(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        add = wFD(self.realm.createGroup(u"somechannel"))
        yield add
        somechannel = add.getResult()

        user.write('JOIN #somechannel\r\n')

        user.transport.clear()
        user.write('MODE #somechannel\r\n')

        response = self._response(user)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][1], '324')
    testGetGroupMode = dG(testGetGroupMode)


    def testSetGroupMode(self):
        user = wFD(self._loggedInUser(u'useruser'))
        yield user
        user = user.getResult()

        group = wFD(self.realm.createGroup(u"groupname"))
        yield group
        group = group.getResult()

        user.write('JOIN #groupname\r\n')

        user.transport.clear()
        user.write('MODE #groupname +abcd\r\n')

        response = self._response(user)
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0][1], '472')
    testSetGroupMode = dG(testSetGroupMode)


    def testWho(self):
        group = service.Group('groupname')
        add = wFD(self.realm.addGroup(group))
        yield add
        add.getResult()

        users = []
        for nick in u'userone', u'usertwo', u'userthree':
            u = wFD(self._loggedInUser(nick))
            yield u
            u = u.getResult()
            users.append(u)
            users[-1].write('JOIN #groupname\r\n')
        for user in users:
            user.transport.clear()

        users[0].write('WHO #groupname\r\n')

        r = self._response(users[0])
        self.failIf(self._response(users[1]))
        self.failIf(self._response(users[2]))

        wantusers = ['userone', 'usertwo', 'userthree']
        for (prefix, code, stuff) in r[:-1]:
            self.assertEqual(prefix, 'realmname')
            self.assertEqual(code, '352')

            (myname, group, theirname, theirhost, theirserver, theirnick, flag, extra) = stuff
            self.assertEqual(myname, 'userone')
            self.assertEqual(group, '#groupname')
            self.failUnless(theirname in wantusers)
            self.assertEqual(theirhost, 'realmname')
            self.assertEqual(theirserver, 'realmname')
            wantusers.remove(theirnick)
            self.assertEqual(flag, 'H')
            self.assertEqual(extra, '0 ' + theirnick)
        self.failIf(wantusers)

        prefix, code, stuff = r[-1]
        self.assertEqual(prefix, 'realmname')
        self.assertEqual(code, '315')
        myname, channel, extra = stuff
        self.assertEqual(myname, 'userone')
        self.assertEqual(channel, '#groupname')
        self.assertEqual(extra, 'End of /WHO list.')
    testWho = dG(testWho)


    def testList(self):
        user = wFD(self._loggedInUser(u"someuser"))
        yield user
        user = user.getResult()
        user.transport.clear()

        somegroup = wFD(self.realm.createGroup(u"somegroup"))
        yield somegroup
        somegroup = somegroup.getResult()
        somegroup.size = lambda: succeed(17)
        somegroup.meta['topic'] = 'this is the topic woo'

        # Test one group
        user.write('LIST #somegroup\r\n')

        r = self._response(user)
        self.assertEqual(len(r), 2)
        resp, end = r

        self.assertEqual(resp[0], 'realmname')
        self.assertEqual(resp[1], '322')
        self.assertEqual(resp[2][0], 'someuser')
        self.assertEqual(resp[2][1], 'somegroup')
        self.assertEqual(resp[2][2], '17')
        self.assertEqual(resp[2][3], 'this is the topic woo')

        self.assertEqual(end[0], 'realmname')
        self.assertEqual(end[1], '323')
        self.assertEqual(end[2][0], 'someuser')
        self.assertEqual(end[2][1], 'End of /LIST')

        user.transport.clear()
        # Test all groups

        user.write('LIST\r\n')
        r = self._response(user)
        self.assertEqual(len(r), 2)

        fg1, end = r

        self.assertEqual(fg1[1], '322')
        self.assertEqual(fg1[2][1], 'somegroup')
        self.assertEqual(fg1[2][2], '17')
        self.assertEqual(fg1[2][3], 'this is the topic woo')

        self.assertEqual(end[1], '323')
    testList = dG(testList)


    def testWhois(self):
        user = wFD(self._loggedInUser(u'someguy'))
        yield user
        user = user.getResult()

        otherguy = service.User("otherguy")
        otherguy.itergroups = lambda: iter([
            service.Group('groupA'),
            service.Group('groupB')])
        otherguy.signOn = 10
        otherguy.lastMessage = time.time() - 15

        add = wFD(self.realm.addUser(otherguy))
        yield add
        add.getResult()

        user.transport.clear()
        user.write('WHOIS otherguy\r\n')
        r = self._response(user)

        self.assertEqual(len(r), 5)
        wuser, wserver, idle, channels, end = r

        self.assertEqual(wuser[0], 'realmname')
        self.assertEqual(wuser[1], '311')
        self.assertEqual(wuser[2][0], 'someguy')
        self.assertEqual(wuser[2][1], 'otherguy')
        self.assertEqual(wuser[2][2], 'otherguy')
        self.assertEqual(wuser[2][3], 'realmname')
        self.assertEqual(wuser[2][4], '*')
        self.assertEqual(wuser[2][5], 'otherguy')

        self.assertEqual(wserver[0], 'realmname')
        self.assertEqual(wserver[1], '312')
        self.assertEqual(wserver[2][0], 'someguy')
        self.assertEqual(wserver[2][1], 'otherguy')
        self.assertEqual(wserver[2][2], 'realmname')
        self.assertEqual(wserver[2][3], 'Hi mom!')

        self.assertEqual(idle[0], 'realmname')
        self.assertEqual(idle[1], '317')
        self.assertEqual(idle[2][0], 'someguy')
        self.assertEqual(idle[2][1], 'otherguy')
        self.assertEqual(idle[2][2], '15')
        self.assertEqual(idle[2][3], '10')
        self.assertEqual(idle[2][4], "seconds idle, signon time")

        self.assertEqual(channels[0], 'realmname')
        self.assertEqual(channels[1], '319')
        self.assertEqual(channels[2][0], 'someguy')
        self.assertEqual(channels[2][1], 'otherguy')
        self.assertEqual(channels[2][2], '#groupA #groupB')

        self.assertEqual(end[0], 'realmname')
        self.assertEqual(end[1], '318')
        self.assertEqual(end[2][0], 'someguy')
        self.assertEqual(end[2][1], 'otherguy')
        self.assertEqual(end[2][2], 'End of WHOIS list.')
    testWhois = dG(testWhois)


class TestMind(service.PBMind):
    def __init__(self, *a, **kw):
        self.joins = []
        self.parts = []
        self.messages = []
        self.meta = []

    def remote_userJoined(self, user, group):
        self.joins.append((user, group))


    def remote_userLeft(self, user, group, reason):
        self.parts.append((user, group, reason))


    def remote_receive(self, sender, recipient, message):
        self.messages.append((sender, recipient, message))


    def remote_groupMetaUpdate(self, group, meta):
        self.meta.append((group, meta))
pb.setUnjellyableForClass(TestMind, service.PBMindReference)


class PBProtocolTestCase(unittest.TestCase):
    def setUp(self):
        self.realm = service.InMemoryWordsRealm("realmname")
        self.checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
        self.portal = portal.Portal(
            self.realm, [self.checker])
        self.serverFactory = pb.PBServerFactory(self.portal)
        self.serverFactory.protocol = self._protocolFactory
        self.serverFactory.unsafeTracebacks = True
        self.clientFactory = pb.PBClientFactory()
        self.clientFactory.unsafeTracebacks = True
        self.serverPort = reactor.listenTCP(0, self.serverFactory)
        self.clientConn = reactor.connectTCP(
            '127.0.0.1',
            self.serverPort.getHost().port,
            self.clientFactory)


    def _protocolFactory(self, *args, **kw):
        self._serverProtocol = pb.Broker(0)
        return self._serverProtocol


    def tearDown(self):
        d3 = Deferred()
        self._serverProtocol.notifyOnDisconnect(lambda: d3.callback(None))
        return DeferredList([
            maybeDeferred(self.serverPort.stopListening),
            maybeDeferred(self.clientConn.disconnect), d3])


    def _loggedInAvatar(self, name, password, mind):
        creds = credentials.UsernamePassword(name, password)
        self.checker.addUser(name.encode('ascii'), password)
        d = self.realm.createUser(name)
        d.addCallback(lambda ign: self.clientFactory.login(creds, mind))
        return d


    def testGroups(self):
        mindone = TestMind()
        one = wFD(self._loggedInAvatar(u"one", "p1", mindone))
        yield one
        one = one.getResult()

        mindtwo = TestMind()
        two = wFD(self._loggedInAvatar(u"two", "p2", mindtwo))
        yield two
        two = two.getResult()

        add = wFD(self.realm.createGroup(u"foobar"))
        yield add
        add.getResult()

        groupone = wFD(one.join(u"foobar"))
        yield groupone
        groupone = groupone.getResult()

        grouptwo = wFD(two.join(u"foobar"))
        yield grouptwo
        grouptwo = grouptwo.getResult()

        msg = wFD(groupone.send({"text": "hello, monkeys"}))
        yield msg
        msg = msg.getResult()

        leave = wFD(groupone.leave())
        yield leave
        leave = leave.getResult()
    testGroups = dG(testGroups)
