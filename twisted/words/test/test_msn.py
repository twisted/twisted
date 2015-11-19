# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.words.protocols.msn}.
"""

import warnings
import StringIO
from hashlib import md5

from twisted.internet.defer import Deferred
from twisted.protocols import loopback
from twisted.python.reflect import requireModule
from twisted.test.proto_helpers import StringTransport, StringIOWithoutClosing
from twisted.trial import unittest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from twisted.words.protocols import msn


def printError(f):
    print f


class PassportTests(unittest.TestCase):

    def setUp(self):
        self.result = []
        self.deferred = Deferred()
        self.deferred.addCallback(lambda r: self.result.append(r))
        self.deferred.addErrback(printError)

    def test_nexus(self):
        """
        When L{msn.PassportNexus} receives enough information to identify the
        address of the login server, it fires the L{Deferred} passed to its
        initializer with that address.
        """
        protocol = msn.PassportNexus(self.deferred, 'https://foobar.com/somepage.quux')
        headers = {
            'Content-Length' : '0',
            'Content-Type'   : 'text/html',
            'PassportURLs'   : 'DARealm=Passport.Net,DALogin=login.myserver.com/,DAReg=reg.myserver.com'
        }
        transport = StringTransport()
        protocol.makeConnection(transport)
        protocol.dataReceived('HTTP/1.0 200 OK\r\n')
        for (h, v) in headers.items():
            protocol.dataReceived('%s: %s\r\n' % (h,v))
        protocol.dataReceived('\r\n')
        self.assertEqual(self.result[0], "https://login.myserver.com/")


    def _doLoginTest(self, response, headers):
        protocol = msn.PassportLogin(self.deferred,'foo@foo.com','testpass','https://foo.com/', 'a')
        protocol.makeConnection(StringTransport())
        protocol.dataReceived(response)
        for (h,v) in headers.items(): protocol.dataReceived('%s: %s\r\n' % (h,v))
        protocol.dataReceived('\r\n')

    def testPassportLoginSuccess(self):
        headers = {
            'Content-Length'      : '0',
            'Content-Type'        : 'text/html',
            'Authentication-Info' : "Passport1.4 da-status=success,tname=MSPAuth," +
                                    "tname=MSPProf,tname=MSPSec,from-PP='somekey'," +
                                    "ru=http://messenger.msn.com"
        }
        self._doLoginTest('HTTP/1.1 200 OK\r\n', headers)
        self.assertTrue(self.result[0] == (msn.LOGIN_SUCCESS, 'somekey'))

    def testPassportLoginFailure(self):
        headers = {
            'Content-Type'     : 'text/html',
            'WWW-Authenticate' : 'Passport1.4 da-status=failed,' +
                                 'srealm=Passport.NET,ts=-3,prompt,cburl=http://host.com,' +
                                 'cbtxt=the%20error%20message'
        }
        self._doLoginTest('HTTP/1.1 401 Unauthorized\r\n', headers)
        self.assertTrue(self.result[0] == (msn.LOGIN_FAILURE, 'the error message'))

    def testPassportLoginRedirect(self):
        headers = {
            'Content-Type'        : 'text/html',
            'Authentication-Info' : 'Passport1.4 da-status=redir',
            'Location'            : 'https://newlogin.host.com/'
        }
        self._doLoginTest('HTTP/1.1 302 Found\r\n', headers)
        self.assertTrue(self.result[0] == (msn.LOGIN_REDIRECT, 'https://newlogin.host.com/', 'a'))


if msn is not None:
    class DummySwitchboardClient(msn.SwitchboardClient):
        def userTyping(self, message):
            self.state = 'TYPING'

        def gotSendRequest(self, fileName, fileSize, cookie, message):
            if fileName == 'foobar.ext' and fileSize == 31337 and cookie == 1234: self.state = 'INVITATION'


    class DummyNotificationClient(msn.NotificationClient):
        def loggedIn(self, userHandle, screenName, verified):
            if userHandle == 'foo@bar.com' and screenName == 'Test Screen Name' and verified:
                self.state = 'LOGIN'

        def gotProfile(self, message):
            self.state = 'PROFILE'

        def gotContactStatus(self, code, userHandle, screenName):
            if code == msn.STATUS_AWAY and userHandle == "foo@bar.com" and screenName == "Test Screen Name":
                self.state = 'INITSTATUS'

        def contactStatusChanged(self, code, userHandle, screenName):
            if code == msn.STATUS_LUNCH and userHandle == "foo@bar.com" and screenName == "Test Name":
                self.state = 'NEWSTATUS'

        def contactOffline(self, userHandle):
            if userHandle == "foo@bar.com": self.state = 'OFFLINE'

        def statusChanged(self, code):
            if code == msn.STATUS_HIDDEN: self.state = 'MYSTATUS'

        def listSynchronized(self, *args):
            self.state = 'GOTLIST'

        def gotPhoneNumber(self, listVersion, userHandle, phoneType, number):
            msn.NotificationClient.gotPhoneNumber(self, listVersion, userHandle, phoneType, number)
            self.state = 'GOTPHONE'

        def userRemovedMe(self, userHandle, listVersion):
            msn.NotificationClient.userRemovedMe(self, userHandle, listVersion)
            c = self.factory.contacts.getContact(userHandle)
            if not c and self.factory.contacts.version == listVersion: self.state = 'USERREMOVEDME'

        def userAddedMe(self, userHandle, screenName, listVersion):
            msn.NotificationClient.userAddedMe(self, userHandle, screenName, listVersion)
            c = self.factory.contacts.getContact(userHandle)
            if c and (c.lists | msn.REVERSE_LIST) and (self.factory.contacts.version == listVersion) and \
               (screenName == 'Screen Name'):
                self.state = 'USERADDEDME'

        def gotSwitchboardInvitation(self, sessionID, host, port, key, userHandle, screenName):
            if sessionID == 1234 and \
               host == '192.168.1.1' and \
               port == 1863 and \
               key == '123.456' and \
               userHandle == 'foo@foo.com' and \
               screenName == 'Screen Name':
                self.state = 'SBINVITED'



class DispatchTests(unittest.TestCase):
    """
    Tests for L{DispatchClient}.
    """
    def _versionTest(self, serverVersionResponse):
        """
        Test L{DispatchClient} version negotiation.
        """
        client = msn.DispatchClient()
        client.userHandle = "foo"

        transport = StringTransport()
        client.makeConnection(transport)
        self.assertEqual(
            transport.value(), "VER 1 MSNP8 CVR0\r\n")
        transport.clear()

        client.dataReceived(serverVersionResponse)
        self.assertEqual(
            transport.value(),
            "CVR 2 0x0409 win 4.10 i386 MSNMSGR 5.0.0544 MSMSGS foo\r\n")


    def test_version(self):
        """
        L{DispatchClient.connectionMade} greets the server with a I{VER}
        (version) message and then L{NotificationClient.dataReceived}
        handles the server's I{VER} response by sending a I{CVR} (client
        version) message.
        """
        self._versionTest("VER 1 MSNP8 CVR0\r\n")


    def test_versionWithoutCVR0(self):
        """
        If the server responds to a I{VER} command without including the
        I{CVR0} protocol, L{DispatchClient} behaves in the same way as if
        that protocol were included.

        Starting in August 2008, CVR0 disappeared from the I{VER} response.
        """
        self._versionTest("VER 1 MSNP8\r\n")



class NotificationTests(unittest.TestCase):
    """ testing the various events in NotificationClient """

    def setUp(self):
        self.client = DummyNotificationClient()
        self.client.factory = msn.NotificationFactory()
        self.client.state = 'START'


    def tearDown(self):
        self.client = None


    def _versionTest(self, serverVersionResponse):
        """
        Test L{NotificationClient} version negotiation.
        """
        self.client.factory.userHandle = "foo"

        transport = StringTransport()
        self.client.makeConnection(transport)
        self.assertEqual(
            transport.value(), "VER 1 MSNP8 CVR0\r\n")
        transport.clear()

        self.client.dataReceived(serverVersionResponse)
        self.assertEqual(
            transport.value(),
            "CVR 2 0x0409 win 4.10 i386 MSNMSGR 5.0.0544 MSMSGS foo\r\n")


    def test_version(self):
        """
        L{NotificationClient.connectionMade} greets the server with a I{VER}
        (version) message and then L{NotificationClient.dataReceived}
        handles the server's I{VER} response by sending a I{CVR} (client
        version) message.
        """
        self._versionTest("VER 1 MSNP8 CVR0\r\n")


    def test_versionWithoutCVR0(self):
        """
        If the server responds to a I{VER} command without including the
        I{CVR0} protocol, L{NotificationClient} behaves in the same way as
        if that protocol were included.

        Starting in August 2008, CVR0 disappeared from the I{VER} response.
        """
        self._versionTest("VER 1 MSNP8\r\n")


    def test_challenge(self):
        """
        L{NotificationClient} responds to a I{CHL} message by sending a I{QRY}
        back which included a hash based on the parameters of the I{CHL}.
        """
        transport = StringTransport()
        self.client.makeConnection(transport)
        transport.clear()

        challenge = "15570131571988941333"
        self.client.dataReceived('CHL 0 ' + challenge + '\r\n')
        # md5 of the challenge and a magic string defined by the protocol
        response = "8f2f5a91b72102cd28355e9fc9000d6e"
        # Sanity check - the response is what the comment above says it is.
        self.assertEqual(
            response, md5(challenge + "Q1P7W2E4J9R8U3S5").hexdigest())
        self.assertEqual(
            transport.value(),
            # 2 is the next transaction identifier.  32 is the length of the
            # response.
            "QRY 2 msmsgs@msnmsgr.com 32\r\n" + response)


    def testLogin(self):
        self.client.lineReceived('USR 1 OK foo@bar.com Test%20Screen%20Name 1 0')
        self.assertTrue((self.client.state == 'LOGIN'), msg='Failed to detect successful login')


    def test_loginWithoutSSLFailure(self):
        """
        L{NotificationClient.loginFailure} is called if the necessary SSL APIs
        are unavailable.
        """
        self.patch(msn, 'ClientContextFactory', None)
        success = []
        self.client.loggedIn = lambda *args: success.append(args)
        failure = []
        self.client.loginFailure = failure.append

        self.client.lineReceived('USR 6 TWN S opaque-string-goes-here')
        self.assertEqual(success, [])
        self.assertEqual(
            failure,
            ["Exception while authenticating: "
             "Connecting to the Passport server requires SSL, but SSL is "
             "unavailable."])


    def testProfile(self):
        m = 'MSG Hotmail Hotmail 353\r\nMIME-Version: 1.0\r\nContent-Type: text/x-msmsgsprofile; charset=UTF-8\r\n'
        m += 'LoginTime: 1016941010\r\nEmailEnabled: 1\r\nMemberIdHigh: 40000\r\nMemberIdLow: -600000000\r\nlang_preference: 1033\r\n'
        m += 'preferredEmail: foo@bar.com\r\ncountry: AU\r\nPostalCode: 90210\r\nGender: M\r\nKid: 0\r\nAge:\r\nsid: 400\r\n'
        m += 'kv: 2\r\nMSPAuth: 2CACCBCCADMoV8ORoz64BVwmjtksIg!kmR!Rj5tBBqEaW9hc4YnPHSOQ$$\r\n\r\n'
        map(self.client.lineReceived, m.split('\r\n')[:-1])
        self.assertTrue((self.client.state == 'PROFILE'), msg='Failed to detect initial profile')

    def testStatus(self):
        t = [('ILN 1 AWY foo@bar.com Test%20Screen%20Name 0', 'INITSTATUS', 'Failed to detect initial status report'),
             ('NLN LUN foo@bar.com Test%20Name 0', 'NEWSTATUS', 'Failed to detect contact status change'),
             ('FLN foo@bar.com', 'OFFLINE', 'Failed to detect contact signing off'),
             ('CHG 1 HDN 0', 'MYSTATUS', 'Failed to detect my status changing')]
        for i in t:
            self.client.lineReceived(i[0])
            self.assertTrue((self.client.state == i[1]), msg=i[2])

    def testListSync(self):
        # currently this test does not take into account the fact
        # that BPRs sent as part of the SYN reply may not be interpreted
        # as such if they are for the last LST -- maybe I should
        # factor this in later.
        self.client.makeConnection(StringTransport())
        msn.NotificationClient.loggedIn(self.client, 'foo@foo.com', 'foobar', 1)
        lines = [
            "SYN %s 100 1 1" % self.client.currentID,
            "GTC A",
            "BLP AL",
            "LSG 0 Other%20Contacts 0",
            "LST userHandle@email.com Some%20Name 11 0"
        ]
        map(self.client.lineReceived, lines)
        contacts = self.client.factory.contacts
        contact = contacts.getContact('userHandle@email.com')
        self.assertTrue(contacts.version == 100, "Invalid contact list version")
        self.assertTrue(contact.screenName == 'Some Name', "Invalid screen-name for user")
        self.assertTrue(contacts.groups == {0 : 'Other Contacts'}, "Did not get proper group list")
        self.assertTrue(contact.groups == [0] and contact.lists == 11, "Invalid contact list/group info")
        self.assertTrue(self.client.state == 'GOTLIST', "Failed to call list sync handler")

    def testAsyncPhoneChange(self):
        c = msn.MSNContact(userHandle='userHandle@email.com')
        self.client.factory.contacts = msn.MSNContactList()
        self.client.factory.contacts.addContact(c)
        self.client.makeConnection(StringTransport())
        self.client.lineReceived("BPR 101 userHandle@email.com PHH 123%20456")
        c = self.client.factory.contacts.getContact('userHandle@email.com')
        self.assertTrue(self.client.state == 'GOTPHONE', "Did not fire phone change callback")
        self.assertTrue(c.homePhone == '123 456', "Did not update the contact's phone number")
        self.assertTrue(self.client.factory.contacts.version == 101, "Did not update list version")

    def testLateBPR(self):
        """
        This test makes sure that if a BPR response that was meant
        to be part of a SYN response (but came after the last LST)
        is received, the correct contact is updated and all is well
        """
        self.client.makeConnection(StringTransport())
        msn.NotificationClient.loggedIn(self.client, 'foo@foo.com', 'foo', 1)
        lines = [
            "SYN %s 100 1 1" % self.client.currentID,
            "GTC A",
            "BLP AL",
            "LSG 0 Other%20Contacts 0",
            "LST userHandle@email.com Some%20Name 11 0",
            "BPR PHH 123%20456"
        ]
        map(self.client.lineReceived, lines)
        contact = self.client.factory.contacts.getContact('userHandle@email.com')
        self.assertTrue(contact.homePhone == '123 456', "Did not update contact's phone number")

    def testUserRemovedMe(self):
        self.client.factory.contacts = msn.MSNContactList()
        contact = msn.MSNContact(userHandle='foo@foo.com')
        contact.addToList(msn.REVERSE_LIST)
        self.client.factory.contacts.addContact(contact)
        self.client.lineReceived("REM 0 RL 100 foo@foo.com")
        self.assertTrue(self.client.state == 'USERREMOVEDME', "Failed to remove user from reverse list")

    def testUserAddedMe(self):
        self.client.factory.contacts = msn.MSNContactList()
        self.client.lineReceived("ADD 0 RL 100 foo@foo.com Screen%20Name")
        self.assertTrue(self.client.state == 'USERADDEDME', "Failed to add user to reverse lise")

    def testAsyncSwitchboardInvitation(self):
        self.client.lineReceived("RNG 1234 192.168.1.1:1863 CKI 123.456 foo@foo.com Screen%20Name")
        self.assertTrue(self.client.state == "SBINVITED")

    def testCommandFailed(self):
        """
        Ensures that error responses from the server fires an errback with
        MSNCommandFailed.
        """
        id, d = self.client._createIDMapping()
        self.client.lineReceived("201 %s" % id)
        d = self.assertFailure(d, msn.MSNCommandFailed)
        def assertErrorCode(exception):
            self.assertEqual(201, exception.errorCode)
        return d.addCallback(assertErrorCode)


class MessageHandlingTests(unittest.TestCase):
    """ testing various message handling methods from SwichboardClient """

    def setUp(self):
        self.client = DummySwitchboardClient()
        self.client.state = 'START'

    def tearDown(self):
        self.client = None

    def testClientCapabilitiesCheck(self):
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-clientcaps')
        self.assertEqual(self.client.checkMessage(m), 0, 'Failed to detect client capability message')

    def testTypingCheck(self):
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgscontrol')
        m.setHeader('TypingUser', 'foo@bar')
        self.client.checkMessage(m)
        self.assertTrue((self.client.state == 'TYPING'), msg='Failed to detect typing notification')

    def testFileInvitation(self, lazyClient=False):
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Application-Name: File Transfer\r\n'
        if not lazyClient:
            m.message += 'Application-GUID: {5D3E02AB-6190-11d3-BBBB-00C04F795683}\r\n'
        m.message += 'Invitation-Command: Invite\r\n'
        m.message += 'Invitation-Cookie: 1234\r\n'
        m.message += 'Application-File: foobar.ext\r\n'
        m.message += 'Application-FileSize: 31337\r\n\r\n'
        self.client.checkMessage(m)
        self.assertTrue((self.client.state == 'INVITATION'), msg='Failed to detect file transfer invitation')

    def testFileInvitationMissingGUID(self):
        return self.testFileInvitation(True)

    def testFileResponse(self):
        d = Deferred()
        d.addCallback(self.fileResponse)
        self.client.cookies['iCookies'][1234] = (d, None)
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Invitation-Command: ACCEPT\r\n'
        m.message += 'Invitation-Cookie: 1234\r\n\r\n'
        self.client.checkMessage(m)
        self.assertTrue((self.client.state == 'RESPONSE'), msg='Failed to detect file transfer response')

    def testFileInfo(self):
        d = Deferred()
        d.addCallback(self.fileInfo)
        self.client.cookies['external'][1234] = (d, None)
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Invitation-Command: ACCEPT\r\n'
        m.message += 'Invitation-Cookie: 1234\r\n'
        m.message += 'IP-Address: 192.168.0.1\r\n'
        m.message += 'Port: 6891\r\n'
        m.message += 'AuthCookie: 4321\r\n\r\n'
        self.client.checkMessage(m)
        self.assertTrue((self.client.state == 'INFO'), msg='Failed to detect file transfer info')

    def fileResponse(self, (accept, cookie, info)):
        if accept and cookie == 1234: self.client.state = 'RESPONSE'

    def fileInfo(self, (accept, ip, port, aCookie, info)):
        if accept and ip == '192.168.0.1' and port == 6891 and aCookie == 4321: self.client.state = 'INFO'


class FileTransferTests(unittest.TestCase):
    """
    test FileSend against FileReceive
    """

    def setUp(self):
        self.input = 'a' * 7000
        self.output = StringIOWithoutClosing()


    def tearDown(self):
        self.input = None
        self.output = None


    def test_fileTransfer(self):
        """
        Test L{FileSend} against L{FileReceive} using a loopback transport.
        """
        auth = 1234
        sender = msn.FileSend(StringIO.StringIO(self.input))
        sender.auth = auth
        sender.fileSize = 7000
        client = msn.FileReceive(auth, "foo@bar.com", self.output)
        client.fileSize = 7000
        def check(ignored):
            self.assertTrue(
                client.completed and sender.completed,
                msg="send failed to complete")
            self.assertEqual(
                self.input, self.output.getvalue(),
                msg="saved file does not match original")
        d = loopback.loopbackAsync(sender, client)
        d.addCallback(check)
        return d



class DeprecationTests(unittest.TestCase):
    """
    Test deprecation of L{twisted.words.protocols.msn}
    """

    def test_deprecation(self):
        """
        Accessing L{twisted.words.protocols.msn} emits a deprecation warning
        """
        requireModule('twisted.words.protocols').msn
        warningsShown = self.flushWarnings([self.test_deprecation])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            'twisted.words.protocols.msn was deprecated in Twisted 15.1.0: ' +
            'MSN has shutdown.')
