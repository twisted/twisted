# -*- test-case-name: twisted.test.test_ftp2 -*-

from cStringIO import StringIO

from twisted.trial import unittest

from twisted.protocols import ftp2 as ftp
from twisted.protocols.ftp2 import RESPONSE, ENDLN
from twisted.cred import portal, credentials, checkers

import zope.interface as zi


class BogusFactory(object):
    allowAnonymous = True
    userAnonymous = 'anonymous'

class BogusTransport(object):
    def __init__(self):
        self.tx = []

    def write(self, arg):
        self.tx.append(arg)

    def clear(self):
        self.tx = []

    def getvalue(self):
        return ''.join(self.tx)
        
class BogusShell(object):
    zi.implements(ftp.IFTPShell)

class BogusRealm(object):
    zi.implements(portal.IRealm)
    def requestAvatar(self, avatarId, mind, *interfaces):
        return ftp.IFTPShell, BogusShell(), None

class TestFTP(unittest.TestCase):
    def setUp(self):
        self.pi = ftp.FTP()
        self.pi.transport = self.tx = BogusTransport()
        self.pi.factory = self.factory = BogusFactory()
        self.pi.portal = portal.Portal(BogusRealm, [checkers.AllowAnonymousAccess])
        self.commands = ['user', 'pass', 'type', 'syst', 'list',
                         'size', 'mdtm', 'pasv', 'pwd', 'port',
                         'cmd', 'cdup', 'retr', 'stru', 'mode', 'quit']

    def failUnlessReplied(self, value, msg=None):
        self.failUnlessEqual(self.tx.getvalue(), value + ENDLN, msg)

    def test_connectionMade(self):
        self.pi.connectionMade()
        self.failUnlessReplied(RESPONSE[ftp.WELCOME_MSG])

    def test_notLoggedIn(self):
        for cmd in self.commands[2:]:
            self.pi.lineReceived(cmd)
            self.failUnlessReplied(RESPONSE[ftp.NOT_LOGGED_IN])
            self.tx.clear()

    def test_USER(self):
        self.failUnlessRaises(ftp.CmdSyntaxError, self.pi.ftp_USER, '')
        self.pi.lineReceived('USER')
        self.failUnlessReplied(RESPONSE[ftp.SYNTAX_ERR] % 'USER')
        self.tx.clear()

        # test anonymous allowed condition
        self.pi.lineReceived('USER anonymous')
        self.failUnlessReplied(RESPONSE[ftp.GUEST_NAME_OK_NEED_EMAIL])
        self.tx.clear()

        # test anonymous not allowed condition
        self.pi.factory.allowAnonymous = False
        usr = 'frylock'
        self.pi.lineReceived('USER %s' % usr)
        self.failUnlessReplied(RESPONSE[ftp.USR_NAME_OK_NEED_PASS] % usr)

    def test_PASS(self):
        self.failUnlessRaises(ftp.BadCmdSequenceError, self.pi.ftp_PASS)
        self.pi.lineReceived('PASS')
        self.failUnlessReplied(RESPONSE[ftp.BAD_CMD_SEQ] % 'USER required before PASS')
        self.tx.clear()

        self.pi.user = 1
        self.pi.lineReceived('PASS')
        self.failUnlessReplied(RESPONSE[ftp.SYNTAX_ERR_IN_ARGS] % 'you must specify a password with PASS')

        # try an anonymous login
        usr = 'anonymous'
        self.pi.user = usr
        import pdb; pdb.set_trace() 
        self.pi.lineReceived('PASS foo@bar.baz.com')
        self.failUnlessReplied(RESPONSE[ftp.GUEST_LOGGED_IN_PROCEED])
