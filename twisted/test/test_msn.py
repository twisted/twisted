# Twisted imports
from twisted.protocols import msn, loopback
from twisted.internet.defer import Deferred
from twisted.trial import unittest

# System imports
import StringIO

class StringIOWithoutClosing(StringIO.StringIO):
    def close(self): pass

class DummySwitchboardClient(msn.MSNSwitchboardClient):
    def userTyping(self, message):
        self.state = 'TYPING'

    def gotSendRequest(self, fileName, fileSize, cookie, message):
        if fileName == 'foobar.ext' and fileSize == 31337 and cookie == 1234: self.state = 'INVITATION'

class DummyNotificationClient(msn.MSNNotificationClient):
    def loggedIn(self, userHandle, screenName, verified):
        if userHandle == 'foo@bar.com' and screenName == 'Test Screen Name' and verified: self.state = 'LOGIN'

    def gotProfile(self, message):
        self.state = 'PROFILE'

    def gotContactStatus(self, code, userHandle, screenName):
        if code == msn.STATUS_AWAY and userHandle == "foo@bar.com" and screenName == "Test Screen Name": self.state = 'INITSTATUS'

    def contactStatusChanged(self, code, userHandle, screenName):
        if code == msn.STATUS_LUNCH and userHandle == "foo@bar.com" and screenName == "Test Name": self.state = 'NEWSTATUS'

    def contactOffline(self, userHandle):
        if userHandle == "foo@bar.com": self.state = 'OFFLINE'

    def statusChanged(self, code):
        if code == msn.STATUS_HIDDEN: self.state = 'MYSTATUS'

class NotificationTests(unittest.TestCase):
    """ testing the various events in MSNNotificationClient """

    def setUp(self):
        self.client = DummyNotificationClient()
        self.client.state = 'START'

    def tearDown(self):
        self.client = None

    def testLogin(self):
        self.client.lineReceived('USR 1 OK foo@bar.com Test%20Screen%20Name 1')
        self.failUnless((self.client.state == 'LOGIN'), message='Failed to detect successful login')

    def testProfile(self):
        m = 'MSG Hotmail Hotmail 353\r\nMIME-Version: 1.0\r\nContent-Type: text/x-msmsgsprofile; charset=UTF-8\r\n'
        m += 'LoginTime: 1016941010\r\nEmailEnabled: 1\r\nMemberIdHigh: 40000\r\nMemberIdLow: -600000000\r\nlang_preference: 1033\r\n'
        m += 'preferredEmail: foo@bar.com\r\ncountry: AU\r\nPostalCode: 90210\r\nGender: M\r\nKid: 0\r\nAge:\r\nsid: 400\r\n'
        m += 'kv: 2\r\nMSPAuth: 2CACCBCCADMoV8ORoz64BVwmjtksIg!kmR!Rj5tBBqEaW9hc4YnPHSOQ$$\r\n\r\n'
        map(self.client.lineReceived, m.split('\r\n')[:-1])
        self.failUnless((self.client.state == 'PROFILE'), message='Failed to detect initial profile')

    def testStatus(self):
        t = [('ILN 1 AWY foo@bar.com Test%20Screen%20Name', 'INITSTATUS', 'Failed to detect initial status report'),
             ('NLN LUN foo@bar.com Test%20Name', 'NEWSTATUS', 'Failed to detect contact status change'),
             ('FLN foo@bar.com', 'OFFLINE', 'Failed to detect contact signing off'),
             ('CHG 1 HDN', 'MYSTATUS', 'Failed to detect my status changing')]
        for i in t:
            self.client.lineReceived(i[0])
            self.failUnless((self.client.state == i[1]), message=i[2])

class MessageHandlingTests(unittest.TestCase):
    """ testing various message handling methods from MSNSwichboardClient """

    def setUp(self):
        self.client = DummySwitchboardClient()
        self.client.state = 'START'

    def tearDown(self):
        self.client = None

    def testTypingCheck(self):
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgscontrol')
        m.setHeader('TypingUser', 'foo@bar')
        self.client.checkMessage(m)
        self.failUnless((self.client.state == 'TYPING'), message='Failed to detect typing notification')

    def testFileInvitation(self):
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Application-Name: File Transfer\r\n'
        m.message += 'Invitation-Command: Invite\r\n'
        m.message += 'Invitation-Cookie: 1234\r\n'
        m.message += 'Application-File: foobar.ext\r\n'
        m.message += 'Application-FileSize: 31337\r\n\r\n'
        self.client.checkMessage(m)
        self.failUnless((self.client.state == 'INVITATION'), message='Failed to detect file transfer invitation')

    def testFileResponse(self):
        d = Deferred()
        d.addCallback(self.fileResponse)
        self.client.cookies['iCookies'][1234] = (d, None)
        m = msn.MSNMessage()
        m.setHeader('Content-Type', 'text/x-msmsgsinvite; charset=UTF-8')
        m.message += 'Invitation-Command: ACCEPT\r\n'
        m.message += 'Invitation-Cookie: 1234\r\n\r\n'
        self.client.checkMessage(m)
        self.failUnless((self.client.state == 'RESPONSE'), message='Failed to detect file transfer response')

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
        self.failUnless((self.client.state == 'INFO'), message='Failed to detect file transfer info')

    def fileResponse(self, (accept, cookie, info)):
        if accept and cookie == 1234: self.client.state = 'RESPONSE'

    def fileInfo(self, (accept, ip, port, aCookie, info)):
        if accept and ip == '192.168.0.1' and port == 6891 and aCookie == 4321: self.client.state = 'INFO'

class FileTransferTestCase(unittest.TestCase):
    """ test MSNFileSend against MSNFileReceive """

    def setUp(self):
        self.input = StringIOWithoutClosing()
        self.input.writelines(['a'] * 7000)
        self.input.seek(0)
        self.output = StringIOWithoutClosing()

    def tearDown(self):
        self.input = None
        self.output = None

    def testFileTransfer(self):
        auth = 1234
        sender = msn.MSNFileSend(self.input)
        sender.auth = auth
        sender.fileSize = 7000
        client = msn.MSNFileReceive(auth, "foo@bar.com", self.output)
        client.fileSize = 7000
        loopback.loopback(sender, client)
        self.failUnless((client.completed and sender.completed), message="send failed to complete")
        self.failUnless((self.input.getvalue() == self.output.getvalue()), message="saved file does not match original")
