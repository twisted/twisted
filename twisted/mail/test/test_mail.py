
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import os
import errno
import md5
import shutil
import smtplib
import pickle
import StringIO
import rfc822

from twisted.trial import unittest
import tempfile

from zope.interface import providedBy, Interface, implements

from twisted.trial import unittest
from twisted.mail import smtp
from twisted.mail import pop3
from twisted.names import dns
from twisted.protocols import basic
from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet.defer import Deferred
from twisted.internet import reactor
from twisted.internet import interfaces
from twisted.internet.error import DNSLookupError, CannotListenError
from twisted.internet import address
from twisted.python import failure
from twisted.python import util

from twisted import mail
import twisted.mail.mail
import twisted.mail.maildir
import twisted.mail.relay
import twisted.mail.relaymanager
import twisted.mail.protocols
import twisted.mail.alias

from twisted.names.error import DNSNameError
from twisted.names.dns import Record_MX

from twisted import cred
import twisted.cred.credentials
import twisted.cred.checkers
import twisted.cred.portal

# Since we run a couple processes, we need SignalMixin from test_process
from twisted.test import test_process

from twisted.test.proto_helpers import LineSendingProtocol

class DomainWithDefaultsTestCase(unittest.TestCase):
    def testMethods(self):
        d = dict([(x, x + 10) for x in range(10)])
        d = mail.mail.DomainWithDefaultDict(d, 'Default')

        self.assertEquals(len(d), 10)
        self.assertEquals(list(iter(d)), range(10))
        self.assertEquals(list(d.iterkeys()), list(iter(d)))

        items = list(d.iteritems())
        items.sort()
        self.assertEquals(items, [(x, x + 10) for x in range(10)])

        values = list(d.itervalues())
        values.sort()
        self.assertEquals(values, range(10, 20))

        items = d.items()
        items.sort()
        self.assertEquals(items, [(x, x + 10) for x in range(10)])

        values = d.values()
        values.sort()
        self.assertEquals(values, range(10, 20))

        for x in range(10):
            self.assertEquals(d[x], x + 10)
            self.assertEquals(d.get(x), x + 10)
            self.failUnless(x in d)
            self.failUnless(d.has_key(x))

        del d[2], d[4], d[6]

        self.assertEquals(len(d), 7)
        self.assertEquals(d[2], 'Default')
        self.assertEquals(d[4], 'Default')
        self.assertEquals(d[6], 'Default')

        d.update({'a': None, 'b': (), 'c': '*'})
        self.assertEquals(len(d), 10)
        self.assertEquals(d['a'], None)
        self.assertEquals(d['b'], ())
        self.assertEquals(d['c'], '*')

        d.clear()
        self.assertEquals(len(d), 0)

        self.assertEquals(d.setdefault('key', 'value'), 'value')
        self.assertEquals(d['key'], 'value')

        self.assertEquals(d.popitem(), ('key', 'value'))
        self.assertEquals(len(d), 0)

class BounceTestCase(unittest.TestCase):
    def setUp(self):
        self.domain = mail.mail.BounceDomain()

    def testExists(self):
        self.assertRaises(smtp.AddressError, self.domain.exists, "any user")

    def testRelay(self):
        self.assertEquals(
            self.domain.willRelay("random q emailer", "protocol"),
            False
        )

    def testMessage(self):
        self.assertRaises(AssertionError, self.domain.startMessage, "whomever")

    def testAddUser(self):
        self.domain.addUser("bob", "password")
        self.assertRaises(smtp.SMTPBadRcpt, self.domain.exists, "bob")

class FileMessageTestCase(unittest.TestCase):
    def setUp(self):
        self.name = "fileMessage.testFile"
        self.final = "final.fileMessage.testFile"
        self.f = file(self.name, 'w')
        self.fp = mail.mail.FileMessage(self.f, self.name, self.final)

    def tearDown(self):
        try:
            self.f.close()
        except:
            pass
        try:
            os.remove(self.name)
        except:
            pass
        try:
            os.remove(self.final)
        except:
            pass

    def testFinalName(self):
        return self.fp.eomReceived().addCallback(self._cbFinalName)
    
    def _cbFinalName(self, result):
        self.assertEquals(result, self.final)
        self.failUnless(self.f.closed)
        self.failIf(os.path.exists(self.name))

    def testContents(self):
        contents = "first line\nsecond line\nthird line\n"
        for line in contents.splitlines():
            self.fp.lineReceived(line)
        self.fp.eomReceived()
        self.assertEquals(file(self.final).read(), contents)

    def testInterrupted(self):
        contents = "first line\nsecond line\n"
        for line in contents.splitlines():
            self.fp.lineReceived(line)
        self.fp.connectionLost()
        self.failIf(os.path.exists(self.name))
        self.failIf(os.path.exists(self.final))

class MailServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = mail.mail.MailService()

    def testFactories(self):
        f = self.service.getPOP3Factory()
        self.failUnless(isinstance(f, protocol.ServerFactory))
        self.failUnless(f.buildProtocol(('127.0.0.1', 12345)), pop3.POP3)

        f = self.service.getSMTPFactory()
        self.failUnless(isinstance(f, protocol.ServerFactory))
        self.failUnless(f.buildProtocol(('127.0.0.1', 12345)), smtp.SMTP)

        f = self.service.getESMTPFactory()
        self.failUnless(isinstance(f, protocol.ServerFactory))
        self.failUnless(f.buildProtocol(('127.0.0.1', 12345)), smtp.ESMTP)

    def testPortals(self):
        o1 = object()
        o2 = object()
        self.service.portals['domain'] = o1
        self.service.portals[''] = o2

        self.failUnless(self.service.lookupPortal('domain') is o1)
        self.failUnless(self.service.defaultPortal() is o2)

class FailingMaildirMailboxAppendMessageTask(mail.maildir._MaildirMailboxAppendMessageTask):
    _openstate = True
    _writestate = True
    _renamestate = True
    def osopen(self, fn, attr, mode):
        if self._openstate:
            return os.open(fn, attr, mode)
        else:
            raise OSError(errno.EPERM, "Faked Permission Problem")
    def oswrite(self, fh, data):
        if self._writestate:
            return os.write(fh, data)
        else:
            raise OSError(errno.ENOSPC, "Faked Space problem")
    def osrename(self, oldname, newname):
        if self._renamestate:
            return os.rename(oldname, newname)
        else:
            raise OSError(errno.EPERM, "Faked Permission Problem")

class MaildirAppendStringTestCase(unittest.TestCase):
    def setUp(self):
        self.d = self.mktemp()
        mail.maildir.initializeMaildir(self.d)

    def tearDown(self):
        shutil.rmtree(self.d)

    def _append(self, ignored, mbox):
        d = mbox.appendMessage('TEST')
        return self.assertFailure(d, Exception)

    def _setState(self, ignored, mbox, rename=None, write=None, open=None):
        if rename is not None:
            mbox.AppendFactory._renameState = rename
        if write is not None:
            mbox.AppendFactory._writeState = write
        if open is not None:
            mbox.AppendFactory._openstate = open

    def testAppend(self):
        mbox = mail.maildir.MaildirMailbox(self.d)
        mbox.AppendFactory = FailingMaildirMailboxAppendMessageTask
        ds = []
        for i in xrange(1, 11):
            ds.append(mbox.appendMessage("X" * i))
            ds[-1].addCallback(self.assertEqual, None)
        d = defer.gatherResults(ds)
        d.addCallback(self._cbTestAppend, mbox)
        return d

    def _cbTestAppend(self, result, mbox):
        self.assertEquals(len(mbox.listMessages()),
                          10)
        self.assertEquals(len(mbox.getMessage(5).read()), 6)
        # test in the right order: last to first error location.
        mbox.AppendFactory._renamestate = False
        d = self._append(None, mbox)
        d.addCallback(self._setState, mbox, rename=True, write=False)
        d.addCallback(self._append, mbox)
        d.addCallback(self._setState, mbox, write=True, open=False)
        d.addCallback(self._append, mbox)
        d.addCallback(self._setState, mbox, open=True)
        return d


class MaildirAppendFileTestCase(unittest.TestCase):
    def setUp(self):
        self.d = self.mktemp()
        mail.maildir.initializeMaildir(self.d)

    def tearDown(self):
        shutil.rmtree(self.d)

    def testAppend(self):
        mbox = mail.maildir.MaildirMailbox(self.d)
        ds = []
        def _check(res, t):
            t.close()
            self.assertEqual(res, None)
        for i in xrange(1, 11):
            temp = tempfile.TemporaryFile()
            temp.write("X" * i)
            temp.seek(0,0)
            ds.append(mbox.appendMessage(temp))
            ds[-1].addCallback(_check, temp)
        return defer.gatherResults(ds).addCallback(self._cbTestAppend, mbox)

    def _cbTestAppend(self, result, mbox):
        self.assertEquals(len(mbox.listMessages()),
                          10)
        self.assertEquals(len(mbox.getMessage(5).read()), 6)


class MaildirTestCase(unittest.TestCase):
    def setUp(self):
        self.d = self.mktemp()
        mail.maildir.initializeMaildir(self.d)

    def tearDown(self):
        shutil.rmtree(self.d)

    def testInitializer(self):
        d = self.d
        trash = os.path.join(d, '.Trash')

        self.failUnless(os.path.exists(d) and os.path.isdir(d))
        self.failUnless(os.path.exists(os.path.join(d, 'new')))
        self.failUnless(os.path.exists(os.path.join(d, 'cur')))
        self.failUnless(os.path.exists(os.path.join(d, 'tmp')))
        self.failUnless(os.path.isdir(os.path.join(d, 'new')))
        self.failUnless(os.path.isdir(os.path.join(d, 'cur')))
        self.failUnless(os.path.isdir(os.path.join(d, 'tmp')))

        self.failUnless(os.path.exists(os.path.join(trash, 'new')))
        self.failUnless(os.path.exists(os.path.join(trash, 'cur')))
        self.failUnless(os.path.exists(os.path.join(trash, 'tmp')))
        self.failUnless(os.path.isdir(os.path.join(trash, 'new')))
        self.failUnless(os.path.isdir(os.path.join(trash, 'cur')))
        self.failUnless(os.path.isdir(os.path.join(trash, 'tmp')))

    def testMailbox(self):
        j = os.path.join
        n = mail.maildir._generateMaildirName
        msgs = [j(b, n()) for b in ('cur', 'new') for x in range(5)]

        # Toss a few files into the mailbox
        i = 1
        for f in msgs:
            f = file(j(self.d, f), 'w')
            f.write('x' * i)
            f.close()
            i = i + 1

        mb = mail.maildir.MaildirMailbox(self.d)
        self.assertEquals(mb.listMessages(), range(1, 11))
        self.assertEquals(mb.listMessages(1), 2)
        self.assertEquals(mb.listMessages(5), 6)

        self.assertEquals(mb.getMessage(6).read(), 'x' * 7)
        self.assertEquals(mb.getMessage(1).read(), 'x' * 2)

        d = {}
        for i in range(10):
            u = mb.getUidl(i)
            self.failIf(u in d)
            d[u] = None

        p, f = os.path.split(msgs[5])

        mb.deleteMessage(5)
        self.assertEquals(mb.listMessages(5), 0)
        self.failUnless(os.path.exists(j(self.d, '.Trash', 'cur', f)))
        self.failIf(os.path.exists(j(self.d, msgs[5])))

        mb.undeleteMessages()
        self.assertEquals(mb.listMessages(5), 6)
        self.failIf(os.path.exists(j(self.d, '.Trash', 'cur', f)))
        self.failUnless(os.path.exists(j(self.d, msgs[5])))

class MaildirDirdbmDomainTestCase(unittest.TestCase):
    def setUp(self):
        self.P = self.mktemp()
        self.S = mail.mail.MailService()
        self.D = mail.maildir.MaildirDirdbmDomain(self.S, self.P)

    def tearDown(self):
        shutil.rmtree(self.P)

    def testAddUser(self):
        toAdd = (('user1', 'pwd1'), ('user2', 'pwd2'), ('user3', 'pwd3'))
        for (u, p) in toAdd:
            self.D.addUser(u, p)

        for (u, p) in toAdd:
            self.failUnless(u in self.D.dbm)
            self.assertEquals(self.D.dbm[u], p)
            self.failUnless(os.path.exists(os.path.join(self.P, u)))

    def testCredentials(self):
        creds = self.D.getCredentialsCheckers()

        self.assertEquals(len(creds), 1)
        self.failUnless(cred.checkers.ICredentialsChecker.providedBy(creds[0]))
        self.failUnless(cred.credentials.IUsernamePassword in creds[0].credentialInterfaces)

    def testRequestAvatar(self):
        class ISomething(Interface):
            pass

        self.D.addUser('user', 'password')
        self.assertRaises(
            NotImplementedError,
            self.D.requestAvatar, 'user', None, ISomething
        )

        t = self.D.requestAvatar('user', None, pop3.IMailbox)
        self.assertEquals(len(t), 3)
        self.failUnless(t[0] is pop3.IMailbox)
        self.failUnless(pop3.IMailbox.providedBy(t[1]))

        t[2]()

    def testRequestAvatarId(self):
        self.D.addUser('user', 'password')
        database = self.D.getCredentialsCheckers()[0]

        creds = cred.credentials.UsernamePassword('user', 'wrong password')
        self.assertRaises(
            cred.error.UnauthorizedLogin,
            database.requestAvatarId, creds
        )

        creds = cred.credentials.UsernamePassword('user', 'password')
        self.assertEquals(database.requestAvatarId(creds), 'user')


class StubAliasableDomain(object):
    """
    Minimal testable implementation of IAliasableDomain.
    """
    implements(mail.mail.IAliasableDomain)

    def exists(self, user):
        """
        No test coverage for invocations of this method on domain objects,
        so we just won't implement it.
        """
        raise NotImplementedError()


    def addUser(self, user, password):
        """
        No test coverage for invocations of this method on domain objects,
        so we just won't implement it.
        """
        raise NotImplementedError()


    def getCredentialsCheckers(self):
        """
        This needs to succeed in order for other tests to complete
        successfully, but we don't actually assert anything about its
        behavior.  Return an empty list.  Sometime later we should return
        something else and assert that a portal got set up properly.
        """
        return []


    def setAliasGroup(self, aliases):
        """
        Just record the value so the test can check it later.
        """
        self.aliasGroup = aliases


class ServiceDomainTestCase(unittest.TestCase):
    def setUp(self):
        self.S = mail.mail.MailService()
        self.D = mail.protocols.DomainDeliveryBase(self.S, None)
        self.D.service = self.S
        self.D.protocolName = 'TEST'
        self.D.host = 'hostname'

        self.tmpdir = self.mktemp()
        domain = mail.maildir.MaildirDirdbmDomain(self.S, self.tmpdir)
        domain.addUser('user', 'password')
        self.S.addDomain('test.domain', domain)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)


    def testAddAliasableDomain(self):
        """
        Test that adding an IAliasableDomain to a mail service properly sets
        up alias group references and such.
        """
        aliases = object()
        domain = StubAliasableDomain()
        self.S.aliases = aliases
        self.S.addDomain('example.com', domain)
        self.assertIdentical(domain.aliasGroup, aliases)


    def testReceivedHeader(self):
         hdr = self.D.receivedHeader(
             ('remotehost', '123.232.101.234'),
             smtp.Address('<someguy@somplace>'),
             ['user@host.name']
         )
         fp = StringIO.StringIO(hdr)
         m = rfc822.Message(fp)
         self.assertEquals(len(m.items()), 1)
         self.failUnless(m.has_key('Received'))

    def testValidateTo(self):
        user = smtp.User('user@test.domain', 'helo', None, 'wherever@whatever')
        return defer.maybeDeferred(self.D.validateTo, user
            ).addCallback(self._cbValidateTo
            )
    
    def _cbValidateTo(self, result):
        self.failUnless(callable(result))

    def testValidateToBadUsername(self):
        user = smtp.User('resu@test.domain', 'helo', None, 'wherever@whatever')
        return self.assertFailure(
            defer.maybeDeferred(self.D.validateTo, user),
            smtp.SMTPBadRcpt)

    def testValidateToBadDomain(self):
        user = smtp.User('user@domain.test', 'helo', None, 'wherever@whatever')
        return self.assertFailure(
            defer.maybeDeferred(self.D.validateTo, user),
            smtp.SMTPBadRcpt)

    def testValidateFrom(self):
        helo = ('hostname', '127.0.0.1')
        origin = smtp.Address('<user@hostname>')
        self.failUnless(self.D.validateFrom(helo, origin) is origin)

        helo = ('hostname', '1.2.3.4')
        origin = smtp.Address('<user@hostname>')
        self.failUnless(self.D.validateFrom(helo, origin) is origin)

        helo = ('hostname', '1.2.3.4')
        origin = smtp.Address('<>')
        self.failUnless(self.D.validateFrom(helo, origin) is origin)

        self.assertRaises(
            smtp.SMTPBadSender,
            self.D.validateFrom, None, origin
        )

class VirtualPOP3TestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = self.mktemp()
        self.S = mail.mail.MailService()
        self.D = mail.maildir.MaildirDirdbmDomain(self.S, self.tmpdir)
        self.D.addUser('user', 'password')
        self.S.addDomain('test.domain', self.D)

        portal = cred.portal.Portal(self.D)
        map(portal.registerChecker, self.D.getCredentialsCheckers())
        self.S.portals[''] = self.S.portals['test.domain'] = portal

        self.P = mail.protocols.VirtualPOP3()
        self.P.service = self.S
        self.P.magic = '<unit test magic>'

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def testAuthenticateAPOP(self):
        resp = md5.new(self.P.magic + 'password').hexdigest()
        return self.P.authenticateUserAPOP('user', resp
            ).addCallback(self._cbAuthenticateAPOP
            )

    def _cbAuthenticateAPOP(self, result):
        self.assertEquals(len(result), 3)
        self.assertEquals(result[0], pop3.IMailbox)
        self.failUnless(pop3.IMailbox.providedBy(result[1]))
        result[2]()

    def testAuthenticateIncorrectUserAPOP(self):
        resp = md5.new(self.P.magic + 'password').hexdigest()
        return self.assertFailure(
            self.P.authenticateUserAPOP('resu', resp),
            cred.error.UnauthorizedLogin)

    def testAuthenticateIncorrectResponseAPOP(self):
        resp = md5.new('wrong digest').hexdigest()
        return self.assertFailure(
            self.P.authenticateUserAPOP('user', resp),
            cred.error.UnauthorizedLogin)

    def testAuthenticatePASS(self):
        return self.P.authenticateUserPASS('user', 'password'
            ).addCallback(self._cbAuthenticatePASS
            )
    
    def _cbAuthenticatePASS(self, result):
        self.assertEquals(len(result), 3)
        self.assertEquals(result[0], pop3.IMailbox)
        self.failUnless(pop3.IMailbox.providedBy(result[1]))
        result[2]()

    def testAuthenticateBadUserPASS(self):
        return self.assertFailure(
            self.P.authenticateUserPASS('resu', 'password'),
            cred.error.UnauthorizedLogin)

    def testAuthenticateBadPasswordPASS(self):
        return self.assertFailure(
            self.P.authenticateUserPASS('user', 'wrong password'),
            cred.error.UnauthorizedLogin)

class empty(smtp.User):
    def __init__(self):
        pass

class RelayTestCase(unittest.TestCase):
    def testExists(self):
        service = mail.mail.MailService()
        domain = mail.relay.DomainQueuer(service)

        doRelay = [
            address.UNIXAddress('/var/run/mail-relay'),
            address.IPv4Address('TCP', '127.0.0.1', 12345),
        ]

        dontRelay = [
            address.IPv4Address('TCP', '192.168.2.1', 62),
            address.IPv4Address('TCP', '1.2.3.4', 1943),
        ]

        for peer in doRelay:
            user = empty()
            user.orig = 'user@host'
            user.dest = 'tsoh@resu'
            user.protocol = empty()
            user.protocol.transport = empty()
            user.protocol.transport.getPeer = lambda: peer

            self.failUnless(callable(domain.exists(user)))

        for peer in dontRelay:
            user = empty()
            user.orig = 'some@place'
            user.protocol = empty()
            user.protocol.transport = empty()
            user.protocol.transport.getPeer = lambda: peer
            user.dest = 'who@cares'

            self.assertRaises(smtp.SMTPBadRcpt, domain.exists, user)

class RelayerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        self.messageFiles = []
        for i in range(10):
            name = os.path.join(self.tmpdir, 'body-%d' % (i,))
            f = file(name + '-H', 'w')
            pickle.dump(['from-%d' % (i,), 'to-%d' % (i,)], f)
            f.close()

            f = file(name + '-D', 'w')
            f.write(name)
            f.seek(0, 0)
            self.messageFiles.append(name)

        self.R = mail.relay.RelayerMixin()
        self.R.loadMessages(self.messageFiles)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def testMailFrom(self):
        for i in range(10):
            self.assertEquals(self.R.getMailFrom(), 'from-%d' % (i,))
            self.R.sentMail(250, None, None, None, None)
        self.assertEquals(self.R.getMailFrom(), None)

    def testMailTo(self):
        for i in range(10):
            self.assertEquals(self.R.getMailTo(), ['to-%d' % (i,)])
            self.R.sentMail(250, None, None, None, None)
        self.assertEquals(self.R.getMailTo(), None)

    def testMailData(self):
        for i in range(10):
            name = os.path.join(self.tmpdir, 'body-%d' % (i,))
            self.assertEquals(self.R.getMailData().read(), name)
            self.R.sentMail(250, None, None, None, None)
        self.assertEquals(self.R.getMailData(), None)

class Manager:
    def __init__(self):
        self.success = []
        self.failure = []
        self.done = []

    def notifySuccess(self, factory, message):
        self.success.append((factory, message))

    def notifyFailure(self, factory, message):
        self.failure.append((factory, message))

    def notifyDone(self, factory):
        self.done.append(factory)

class ManagedRelayerTestCase(unittest.TestCase):
    def setUp(self):
        self.manager = Manager()
        self.messages = range(0, 20, 2)
        self.factory = object()
        self.relay = mail.relaymanager.ManagedRelayerMixin(self.manager)
        self.relay.messages = self.messages[:]
        self.relay.names = self.messages[:]
        self.relay.factory = self.factory

    def testSuccessfulSentMail(self):
        for i in self.messages:
            self.relay.sentMail(250, None, None, None, None)

        self.assertEquals(
            self.manager.success,
            [(self.factory, m) for m in self.messages]
        )

    def testFailedSentMail(self):
        for i in self.messages:
            self.relay.sentMail(550, None, None, None, None)

        self.assertEquals(
            self.manager.failure,
            [(self.factory, m) for m in self.messages]
        )

    def testConnectionLost(self):
        self.relay.connectionLost(failure.Failure(Exception()))
        self.assertEquals(self.manager.done, [self.factory])

class DirectoryQueueTestCase(unittest.TestCase):
    def setUp(self):
        # This is almost a test case itself.
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        self.queue = mail.relaymanager.Queue(self.tmpdir)
        self.queue.noisy = False
        for m in range(25):
            hdrF, msgF = self.queue.createNewMessage()
            pickle.dump(['header', m], hdrF)
            hdrF.close()
            msgF.lineReceived('body: %d' % (m,))
            msgF.eomReceived()
        self.queue.readDirectory()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def testWaiting(self):
        self.failUnless(self.queue.hasWaiting())
        self.assertEquals(len(self.queue.getWaiting()), 25)

        waiting = self.queue.getWaiting()
        self.queue.setRelaying(waiting[0])
        self.assertEquals(len(self.queue.getWaiting()), 24)

        self.queue.setWaiting(waiting[0])
        self.assertEquals(len(self.queue.getWaiting()), 25)

    def testRelaying(self):
        for m in self.queue.getWaiting():
            self.queue.setRelaying(m)
            self.assertEquals(
                len(self.queue.getRelayed()),
                25 - len(self.queue.getWaiting())
            )

        self.failIf(self.queue.hasWaiting())

        relayed = self.queue.getRelayed()
        self.queue.setWaiting(relayed[0])
        self.assertEquals(len(self.queue.getWaiting()), 1)
        self.assertEquals(len(self.queue.getRelayed()), 24)

    def testDone(self):
        msg = self.queue.getWaiting()[0]
        self.queue.setRelaying(msg)
        self.queue.done(msg)

        self.assertEquals(len(self.queue.getWaiting()), 24)
        self.assertEquals(len(self.queue.getRelayed()), 0)

        self.failIf(msg in self.queue.getWaiting())
        self.failIf(msg in self.queue.getRelayed())

    def testEnvelope(self):
        envelopes = []

        for msg in self.queue.getWaiting():
            envelopes.append(self.queue.getEnvelope(msg))

        envelopes.sort()
        for i in range(25):
            self.assertEquals(
                envelopes.pop(0),
                ['header', i]
            )

from twisted.names import server
from twisted.names import client
from twisted.names import common

class TestAuthority(common.ResolverBase):
    def __init__(self):
        common.ResolverBase.__init__(self)
        self.addresses = {}

    def _lookup(self, name, cls, type, timeout = None):
        if name in self.addresses and type == dns.MX:
            results = []
            for a in self.addresses[name]:
                hdr = dns.RRHeader(
                    name, dns.MX, dns.IN, 60, dns.Record_MX(0, a)
                )
                results.append(hdr)
            return defer.succeed((results, [], []))
        return defer.fail(failure.Failure(dns.DomainError(name)))

def setUpDNS(self):
    self.auth = TestAuthority()
    factory = server.DNSServerFactory([self.auth])
    protocol = dns.DNSDatagramProtocol(factory)
    while 1:
        self.port = reactor.listenTCP(0, factory, interface='127.0.0.1')
        portNumber = self.port.getHost().port

        try:
            self.udpPort = reactor.listenUDP(portNumber, protocol, interface='127.0.0.1')
        except CannotListenError:
            self.port.stopListening()
        else:
            break
    self.resolver = client.Resolver(servers=[('127.0.0.1', portNumber)])


def tearDownDNS(self):
    dl = []
    dl.append(defer.maybeDeferred(self.port.stopListening))
    dl.append(defer.maybeDeferred(self.udpPort.stopListening))
    if self.resolver.protocol.transport is not None:
        dl.append(defer.maybeDeferred(self.resolver.protocol.transport.stopListening))
    try:
        self.resolver._parseCall.cancel()
    except:
        pass
    return defer.DeferredList(dl)

class MXTestCase(unittest.TestCase):
    def setUp(self):
        setUpDNS(self)
        self.mx = mail.relaymanager.MXCalculator(self.resolver)

    def tearDown(self):
        return tearDownDNS(self)

    def testSimpleSuccess(self):
        self.auth.addresses['test.domain'] = ['the.email.test.domain']
        return self.mx.getMX('test.domain').addCallback(self._cbSimpleSuccess)

    def _cbSimpleSuccess(self, mx):
        self.assertEquals(mx.preference, 0)
        self.assertEquals(str(mx.name), 'the.email.test.domain')

    def testSimpleFailure(self):
        self.mx.fallbackToDomain = False
        return self.assertFailure(self.mx.getMX('test.domain'), IOError)

    def testSimpleFailureWithFallback(self):
        return self.assertFailure(self.mx.getMX('test.domain'), DNSLookupError)


    def test_failureWithSuccessfulFallback(self):
        """
        Test that if the MX record lookup fails, fallback is enabled, and an A
        record is available for the name, then the Deferred returned by
        L{MXCalculator.getMX} ultimately fires with a Record_MX instance which
        gives the address in the A record for the name.
        """
        class DummyResolver(object):
            """
            Fake resolver which will fail an MX lookup but then succeed a
            getHostByName call.
            """
            def lookupMailExchange(self, domain):
                return defer.fail(DNSNameError())

            def getHostByName(self, domain):
                return defer.succeed("1.2.3.4")

        self.mx.resolver = DummyResolver()
        d = self.mx.getMX("domain")
        d.addCallback(self.assertEqual, Record_MX(name="1.2.3.4"))
        return d


    def testManyRecords(self):
        self.auth.addresses['test.domain'] = [
            'mx1.test.domain', 'mx2.test.domain', 'mx3.test.domain'
        ]
        return self.mx.getMX('test.domain'
            ).addCallback(self._cbManyRecordsSuccessfulLookup
            )
    
    def _cbManyRecordsSuccessfulLookup(self, mx):
        self.failUnless(str(mx.name).split('.', 1)[0] in ('mx1', 'mx2', 'mx3'))
        self.mx.markBad(str(mx.name))
        return self.mx.getMX('test.domain'
            ).addCallback(self._cbManyRecordsDifferentResult, mx
            )
    
    def _cbManyRecordsDifferentResult(self, nextMX, mx):
        self.assertNotEqual(str(mx.name), str(nextMX.name))
        self.mx.markBad(str(nextMX.name))

        return self.mx.getMX('test.domain'
            ).addCallback(self._cbManyRecordsLastResult, mx, nextMX
            )
    
    def _cbManyRecordsLastResult(self, lastMX, mx, nextMX):
        self.assertNotEqual(str(mx.name), str(lastMX.name))
        self.assertNotEqual(str(nextMX.name), str(lastMX.name))

        self.mx.markBad(str(lastMX.name))
        self.mx.markGood(str(nextMX.name))
        
        return self.mx.getMX('test.domain'
            ).addCallback(self._cbManyRecordsRepeatSpecificResult, nextMX
            )
    
    def _cbManyRecordsRepeatSpecificResult(self, againMX, nextMX):
        self.assertEqual(str(againMX.name), str(nextMX.name))

class LiveFireExercise(unittest.TestCase):
    if interfaces.IReactorUDP(reactor, None) is None:
        skip = "UDP support is required to determining MX records"

    def setUp(self):
        setUpDNS(self)
        self.tmpdirs = [
            'domainDir', 'insertionDomain', 'insertionQueue',
            'destinationDomain', 'destinationQueue'
        ]

    def tearDown(self):
        for d in self.tmpdirs:
            if os.path.exists(d):
                shutil.rmtree(d)
        return tearDownDNS(self)

    def testLocalDelivery(self):
        service = mail.mail.MailService()
        service.smtpPortal.registerChecker(cred.checkers.AllowAnonymousAccess())
        domain = mail.maildir.MaildirDirdbmDomain(service, 'domainDir')
        domain.addUser('user', 'password')
        service.addDomain('test.domain', domain)
        service.portals[''] = service.portals['test.domain']
        map(service.portals[''].registerChecker, domain.getCredentialsCheckers())

        service.setQueue(mail.relay.DomainQueuer(service))
        manager = mail.relaymanager.SmartHostSMTPRelayingManager(service.queue, None)
        helper = mail.relaymanager.RelayStateHelper(manager, 1)

        f = service.getSMTPFactory()

        self.smtpServer = reactor.listenTCP(0, f, interface='127.0.0.1')

        client = LineSendingProtocol([
            'HELO meson',
            'MAIL FROM: <user@hostname>',
            'RCPT TO: <user@test.domain>',
            'DATA',
            'This is the message',
            '.',
            'QUIT'
        ])

        done = Deferred()
        f = protocol.ClientFactory()
        f.protocol = lambda: client
        f.clientConnectionLost = lambda *args: done.callback(None)
        reactor.connectTCP('127.0.0.1', self.smtpServer.getHost().port, f)

        def finished(ign):
            mbox = domain.requestAvatar('user', None, pop3.IMailbox)[1]
            msg = mbox.getMessage(0).read()
            self.failIfEqual(msg.find('This is the message'), -1)

            return self.smtpServer.stopListening()
        done.addCallback(finished)
        return done


    def testRelayDelivery(self):
        # Here is the service we will connect to and send mail from
        insServ = mail.mail.MailService()
        insServ.smtpPortal.registerChecker(cred.checkers.AllowAnonymousAccess())
        domain = mail.maildir.MaildirDirdbmDomain(insServ, 'insertionDomain')
        insServ.addDomain('insertion.domain', domain)
        os.mkdir('insertionQueue')
        insServ.setQueue(mail.relaymanager.Queue('insertionQueue'))
        insServ.domains.setDefaultDomain(mail.relay.DomainQueuer(insServ))
        manager = mail.relaymanager.SmartHostSMTPRelayingManager(insServ.queue)
        manager.fArgs += ('test.identity.hostname',)
        helper = mail.relaymanager.RelayStateHelper(manager, 1)
        # Yoink!  Now the internet obeys OUR every whim!
        manager.mxcalc = mail.relaymanager.MXCalculator(self.resolver)
        # And this is our whim.
        self.auth.addresses['destination.domain'] = ['127.0.0.1']

        f = insServ.getSMTPFactory()
        self.insServer = reactor.listenTCP(0, f, interface='127.0.0.1')

        # Here is the service the previous one will connect to for final
        # delivery
        destServ = mail.mail.MailService()
        destServ.smtpPortal.registerChecker(cred.checkers.AllowAnonymousAccess())
        domain = mail.maildir.MaildirDirdbmDomain(destServ, 'destinationDomain')
        domain.addUser('user', 'password')
        destServ.addDomain('destination.domain', domain)
        os.mkdir('destinationQueue')
        destServ.setQueue(mail.relaymanager.Queue('destinationQueue'))
        manager2 = mail.relaymanager.SmartHostSMTPRelayingManager(destServ.queue)
        helper = mail.relaymanager.RelayStateHelper(manager, 1)
        helper.startService()

        f = destServ.getSMTPFactory()
        self.destServer = reactor.listenTCP(0, f, interface='127.0.0.1')

        # Update the port number the *first* relay will connect to, because we can't use
        # port 25
        manager.PORT = self.destServer.getHost().port

        client = LineSendingProtocol([
            'HELO meson',
            'MAIL FROM: <user@wherever>',
            'RCPT TO: <user@destination.domain>',
            'DATA',
            'This is the message',
            '.',
            'QUIT'
        ])

        done = Deferred()
        f = protocol.ClientFactory()
        f.protocol = lambda: client
        f.clientConnectionLost = lambda *args: done.callback(None)
        reactor.connectTCP('127.0.0.1', self.insServer.getHost().port, f)

        def finished(ign):
            # First part of the delivery is done.  Poke the queue manually now
            # so we don't have to wait for the queue to be flushed.
            delivery = manager.checkState()
            def delivered(ign):
                mbox = domain.requestAvatar('user', None, pop3.IMailbox)[1]
                msg = mbox.getMessage(0).read()
                self.failIfEqual(msg.find('This is the message'), -1)

                self.insServer.stopListening()
                self.destServer.stopListening()
                helper.stopService()
            delivery.addCallback(delivered)
            return delivery
        done.addCallback(finished)
        return done


aliasFile = StringIO.StringIO("""\
# Here's a comment
   # woop another one
testuser:                   address1,address2, address3,
    continuation@address, |/bin/process/this

usertwo:thisaddress,thataddress, lastaddress
lastuser:       :/includable, /filename, |/program, address
""")

class LineBufferMessage:
    def __init__(self):
        self.lines = []
        self.eom = False
        self.lost = False

    def lineReceived(self, line):
        self.lines.append(line)

    def eomReceived(self):
        self.eom = True
        return defer.succeed('<Whatever>')

    def connectionLost(self):
        self.lost = True

class AliasTestCase(unittest.TestCase):
    lines = [
        'First line',
        'Next line',
        '',
        'After a blank line',
        'Last line'
    ]

    def setUp(self):
        aliasFile.seek(0)

    def testHandle(self):
        result = {}
        lines = [
            'user:  another@host\n',
            'nextuser:  |/bin/program\n',
            'user:  me@again\n',
            'moreusers: :/etc/include/filename\n',
            'multiuser: first@host, second@host,last@anotherhost',
        ]

        for l in lines:
            mail.alias.handle(result, l, 'TestCase', None)

        self.assertEquals(result['user'], ['another@host', 'me@again'])
        self.assertEquals(result['nextuser'], ['|/bin/program'])
        self.assertEquals(result['moreusers'], [':/etc/include/filename'])
        self.assertEquals(result['multiuser'], ['first@host', 'second@host', 'last@anotherhost'])

    def testFileLoader(self):
        domains = {'': object()}
        result = mail.alias.loadAliasFile(domains, fp=aliasFile)

        self.assertEquals(len(result), 3)

        group = result['testuser']
        s = str(group)
        for a in ('address1', 'address2', 'address3', 'continuation@address', '/bin/process/this'):
            self.failIfEqual(s.find(a), -1)
        self.assertEquals(len(group), 5)

        group = result['usertwo']
        s = str(group)
        for a in ('thisaddress', 'thataddress', 'lastaddress'):
            self.failIfEqual(s.find(a), -1)
        self.assertEquals(len(group), 3)

        group = result['lastuser']
        s = str(group)
        self.failUnlessEqual(s.find('/includable'), -1)
        for a in ('/filename', 'program', 'address'):
            self.failIfEqual(s.find(a), -1, '%s not found' % a)
        self.assertEquals(len(group), 3)

    def testMultiWrapper(self):
        msgs = LineBufferMessage(), LineBufferMessage(), LineBufferMessage()
        msg = mail.alias.MultiWrapper(msgs)

        for L in self.lines:
            msg.lineReceived(L)
        return msg.eomReceived().addCallback(self._cbMultiWrapper, msgs)

    def _cbMultiWrapper(self, ignored, msgs):
        for m in msgs:
            self.failUnless(m.eom)
            self.failIf(m.lost)
            self.assertEquals(self.lines, m.lines)

    def testFileAlias(self):
        tmpfile = self.mktemp()
        a = mail.alias.FileAlias(tmpfile, None, None)
        m = a.createMessageReceiver()

        for l in self.lines:
            m.lineReceived(l)
        return m.eomReceived().addCallback(self._cbTestFileAlias, tmpfile)

    def _cbTestFileAlias(self, ignored, tmpfile):
        lines = file(tmpfile).readlines()
        self.assertEquals([L[:-1] for L in lines], self.lines)


class DummyProcess(object):
    __slots__ = ['onEnd']

class ProcessAliasTestCase(test_process.SignalMixin, unittest.TestCase):
    lines = [
        'First line',
        'Next line',
        '',
        'After a blank line',
        'Last line'
    ]

    def setUpClass(self):
        self.DNSNAME = smtp.DNSNAME
        smtp.DNSNAME = ''

    def tearDownClass(self):
        smtp.DNSNAME = self.DNSNAME

    def testProcessAlias(self):
        path = util.sibpath(__file__, 'process.alias.sh')
        a = mail.alias.ProcessAlias(path, None, None)
        m = a.createMessageReceiver()

        for l in self.lines:
            m.lineReceived(l)
        return m.eomReceived().addCallback(self._cbProcessAlias)

    def _cbProcessAlias(self, ignored):
        lines = file('process.alias.out').readlines()
        self.assertEquals([L[:-1] for L in lines], self.lines)

    def testAliasResolution(self):
        aliases = {}
        domain = {'': TestDomain(aliases, ['user1', 'user2', 'user3'])}
        A1 = mail.alias.AliasGroup(['user1', '|echo', '/file'], domain, 'alias1')
        A2 = mail.alias.AliasGroup(['user2', 'user3'], domain, 'alias2')
        A3 = mail.alias.AddressAlias('alias1', domain, 'alias3')
        aliases.update({
            'alias1': A1,
            'alias2': A2,
            'alias3': A3,
        })

        r1 = map(str, A1.resolve(aliases).objs)
        r1.sort()
        expected = map(str, [
            mail.alias.AddressAlias('user1', None, None),
            mail.alias.MessageWrapper(DummyProcess(), 'echo'),
            mail.alias.FileWrapper('/file'),
        ])
        expected.sort()
        self.assertEquals(r1, expected)

        r2 = map(str, A2.resolve(aliases).objs)
        r2.sort()
        expected = map(str, [
            mail.alias.AddressAlias('user2', None, None),
            mail.alias.AddressAlias('user3', None, None)
        ])
        expected.sort()
        self.assertEquals(r2, expected)

        r3 = map(str, A3.resolve(aliases).objs)
        r3.sort()
        expected = map(str, [
            mail.alias.AddressAlias('user1', None, None),
            mail.alias.MessageWrapper(DummyProcess(), 'echo'),
            mail.alias.FileWrapper('/file'),
        ])
        expected.sort()
        self.assertEquals(r3, expected)

    def testCyclicAlias(self):
        aliases = {}
        domain = {'': TestDomain(aliases, [])}
        A1 = mail.alias.AddressAlias('alias2', domain, 'alias1')
        A2 = mail.alias.AddressAlias('alias3', domain, 'alias2')
        A3 = mail.alias.AddressAlias('alias1', domain, 'alias3')
        aliases.update({
            'alias1': A1,
            'alias2': A2,
            'alias3': A3
        })

        self.assertEquals(aliases['alias1'].resolve(aliases), None)
        self.assertEquals(aliases['alias2'].resolve(aliases), None)
        self.assertEquals(aliases['alias3'].resolve(aliases), None)

        A4 = mail.alias.AliasGroup(['|echo', 'alias1'], domain, 'alias4')
        aliases['alias4'] = A4
        
        r = map(str, A4.resolve(aliases).objs)
        r.sort()
        expected = map(str, [
            mail.alias.MessageWrapper(DummyProcess(), 'echo')
        ])

if interfaces.IReactorProcess(reactor, None) is None:
    ProcessAliasTestCase = "IReactorProcess not supported"

class TestDomain:
    def __init__(self, aliases, users):
        self.aliases = aliases
        self.users = users

    def exists(self, user, memo=None):
        user = user.dest.local
        if user in self.users:
            return lambda: mail.alias.AddressAlias(user, None, None)
        try:
            a = self.aliases[user]
        except:
            raise smtp.SMTPBadRcpt(user)
        else:
            aliases = a.resolve(self.aliases, memo)
            if aliases:
                return lambda: aliases
            raise smtp.SMTPBadRcpt(user)


from twisted.python.runtime import platformType
import types
if platformType != "posix":
    for o in locals().values():
        if isinstance(o, (types.ClassType, type)) and issubclass(o, unittest.TestCase):
            o.skip = "twisted.mail only works on posix"
