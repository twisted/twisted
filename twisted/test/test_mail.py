
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

import os
import md5
import shutil
import smtplib
import pickle
import StringIO
import rfc822

from twisted.trial import unittest
from twisted.protocols import smtp
from twisted.protocols import pop3
from twisted.protocols import dns
from twisted.protocols import basic
from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import interfaces
from twisted.internet.error import DNSLookupError, CannotListenError
from twisted.python import components
from twisted.python import failure
from twisted.python import util

from twisted import mail
import twisted.mail.mail
import twisted.mail.maildir
import twisted.mail.relay
import twisted.mail.relaymanager
import twisted.mail.protocols
import twisted.mail.alias

from twisted import cred
import twisted.cred.credentials
import twisted.cred.checkers
import twisted.cred.portal

# Since we run a couple processes, we need SignalMixin from test_process
import test_process

from proto_helpers import LineSendingProtocol

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
        self.assertEquals(unittest.deferredResult(self.fp.eomReceived()), self.final)
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
        self.failUnless(components.implements(creds[0], cred.checkers.ICredentialsChecker))
        self.failUnless(cred.credentials.IUsernamePassword in creds[0].credentialInterfaces)
    
    def testRequestAvatar(self):
        class ISomething(components.Interface):
            pass
        
        self.D.addUser('user', 'password')
        self.assertRaises(
            NotImplementedError,
            self.D.requestAvatar, 'user', None, ISomething
        )
        
        t = self.D.requestAvatar('user', None, pop3.IMailbox)
        self.assertEquals(len(t), 3)
        self.failUnless(t[0] is pop3.IMailbox)
        self.failUnless(components.implements(t[1], pop3.IMailbox))
        
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
        self.S.domains['test.domain'] = domain

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

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
        self.failUnless(
            callable(unittest.deferredResult(
                defer.maybeDeferred(self.D.validateTo, user)
            ))
        )
        user = smtp.User('resu@test.domain', 'helo', None, 'wherever@whatever')
        self.assertEquals(
            unittest.deferredResult(
                self.D.validateTo(user).addErrback(
                    lambda f: f.trap(smtp.SMTPBadRcpt)
                )
            ), smtp.SMTPBadRcpt
        )

        user = smtp.User('user@domain.test', 'helo', None, 'wherever@whatever')
        self.assertEquals(
            unittest.deferredResult(
                self.D.validateTo(user).addErrback(
                    lambda f: f.trap(smtp.SMTPBadRcpt)
                )
            ), smtp.SMTPBadRcpt
        )
    
    def testValidateFrom(self):
        helo = ('hostname', '127.0.0.1')
        origin = smtp.Address('<user@hostname>')
        self.failUnless(self.D.validateFrom(helo, origin) is origin)
        
        helo = ('hostname', '1.2.3.4')
        origin = smtp.Address('<user@hostname>')
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
        self.S.domains['test.domain'] = self.D
        
        portal = cred.portal.Portal(self.D)
        map(portal.registerChecker, self.D.getCredentialsCheckers())
        self.S.portals[''] = self.S.portals['test.domain'] = portal
        

        self.P = mail.protocols.VirtualPOP3()
        self.P.service = self.S
        self.P.magic = '<unit test magic>'
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir)
    
    def testAuthenticateAPOP(self):
        result = unittest.deferredResult(
            self.P.authenticateUserAPOP(
                'user',
                md5.new(self.P.magic + 'password').hexdigest()
            )
        )
        
        self.assertEquals(len(result), 3)
        self.assertEquals(result[0], pop3.IMailbox)
        self.failUnless(components.implements(result[1], pop3.IMailbox))
        result[2]()
        
        self.assertEquals(
            unittest.deferredResult(
                self.P.authenticateUserAPOP(
                    'resu',
                    md5.new(self.P.magic + 'password').hexdigest()
                ).addErrback(lambda f: f.trap(cred.error.UnauthorizedLogin))
            ), cred.error.UnauthorizedLogin
        )
        
        self.assertEquals(
            unittest.deferredResult(
                self.P.authenticateUserAPOP(
                    'user',
                    md5.new('wrong digest').hexdigest()
                ).addErrback(lambda f: f.trap(cred.error.UnauthorizedLogin))
            ), cred.error.UnauthorizedLogin
        )

    def testAuthenticatePASS(self):
        result = unittest.deferredResult(
            self.P.authenticateUserPASS(
                'user',
                'password'
            )
        )
        
        self.assertEquals(len(result), 3)
        self.assertEquals(result[0], pop3.IMailbox)
        self.failUnless(components.implements(result[1], pop3.IMailbox))
        result[2]()
        
        self.assertEquals(
            unittest.deferredResult(
                self.P.authenticateUserPASS(
                    'resu', 'password'
                ).addErrback(lambda f: f.trap(cred.error.UnauthorizedLogin))
            ), cred.error.UnauthorizedLogin
        )
        
        self.assertEquals(
            unittest.deferredResult(
                self.P.authenticateUserPASS(
                    'user', 'wrong password'
                ).addErrback(lambda f: f.trap(cred.error.UnauthorizedLogin))
            ), cred.error.UnauthorizedLogin
        )

class empty(smtp.User):
    def __init__(self):
        pass

class RelayTestCase(unittest.TestCase):
    def testExists(self):
        service = mail.mail.MailService()
        domain = mail.relay.DomainQueuer(service)
        
        doRelay = [
            ('UNIX', '/var/run/mail-relay'),
            ('TCP', '127.0.0.1', 12345),
        ]
        
        dontRelay = [
            ('TCP', '192.168.2.1', 62),
            ('TCP', '1.2.3.4', 1943),
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
        portNumber = self.port.getHost()[2]
        
        try:
            self.udpPort = reactor.listenUDP(portNumber, protocol, interface='127.0.0.1')
        except CannotListenError:
            self.port.stopListening()
        else:
            break
    self.resolver = client.Resolver(servers=[('127.0.0.1', portNumber)])

def tearDownDNS(self):
    self.port.stopListening()
    self.udpPort.stopListening()
    try:
        self.resolver._parseCall.cancel()
    except:
        pass

class MXTestCase(unittest.TestCase):
    def setUp(self):
        setUpDNS(self)
        self.mx = mail.relaymanager.MXCalculator(self.resolver)
    
    def tearDown(self):
        tearDownDNS(self)
    
    def testSimpleSuccess(self):
        self.auth.addresses['test.domain'] = ['the.email.test.domain']
        
        mx = unittest.deferredResult(self.mx.getMX('test.domain'))
        self.assertEquals(mx.preference, 0)
        self.assertEquals(str(mx.exchange), 'the.email.test.domain')
    
    def testSimpleFailure(self):
        self.mx.fallbackToDomain = False
        self.assertEquals(
            unittest.deferredError(self.mx.getMX('test.domain')).type,
            IOError
        )

    def testSimpleFailureWithFallback(self):
        self.assertEquals(
            unittest.deferredError(self.mx.getMX('test.domain')).type,
            DNSLookupError
        )
    
    def testManyRecords(self):
        self.auth.addresses['test.domain'] = [
            'mx1.test.domain', 'mx2.test.domain', 'mx3.test.domain'
        ]
        
        mx = unittest.deferredResult(self.mx.getMX('test.domain'))
        self.failUnless(str(mx.exchange).split('.', 1)[0] in ('mx1', 'mx2', 'mx3'))
        
        self.mx.markBad(mx)
        
        nextMX = unittest.deferredResult(self.mx.getMX('test.domain'))
        self.assertNotEqual(str(mx.exchange), str(nextMX.exchange))
        
        self.mx.markBad(nextMX)
        
        lastMX = unittest.deferredResult(self.mx.getMX('test.domain'))
        self.assertNotEqual(str(mx.exchange), str(lastMX.exchange))
        self.assertNotEqual(str(nextMX.exchange), str(lastMX.exchange))
        
        self.mx.markBad(lastMX)
        self.mx.markGood(nextMX)
        
        againMX = unittest.deferredResult(self.mx.getMX('test.domain'))
        self.assertEqual(str(againMX.exchange), str(nextMX.exchange))

class LiveFireExercise(unittest.TestCase):
    if interfaces.IReactorUDP(reactor, default=None) is None:
        skip = "UDP support is required to determining MX records"

    def setUp(self):
        setUpDNS(self)
        self.tmpdirs = [
            'domainDir', 'insertionDomain', 'insertionQueue',
            'destinationDomain', 'destinationQueue'
        ]

    def tearDown(self):
        tearDownDNS(self)
        for d in self.tmpdirs:
            if os.path.exists(d):
                shutil.rmtree(d)

    def testLocalDelivery(self):
        service = mail.mail.MailService()
        service.smtpPortal.registerChecker(cred.checkers.AllowAnonymousAccess())
        domain = mail.maildir.MaildirDirdbmDomain(service, 'domainDir')
        domain.addUser('user', 'password')
        service.domains['test.domain'] = domain
        service.portals['test.domain'] = cred.portal.Portal(domain)
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
        
        done = []
        f = protocol.ClientFactory()
        f.protocol = lambda: client
        f.clientConnectionLost = lambda *args: done.append(None)
        reactor.connectTCP('127.0.0.1', self.smtpServer.getHost()[2], f)

        i = 0
        while len(done) == 0 and i < 1000:
            reactor.iterate(0.01)
            i += 1
        
        self.failUnless(done)
        
        mbox = domain.requestAvatar('user', None, pop3.IMailbox)[1]
        msg = mbox.getMessage(0).read()
        self.failIfEqual(msg.find('This is the message'), -1)
        
        self.smtpServer.stopListening()

    def testRelayDelivery(self):
        # Here is the service we will connect to and send mail from
        insServ = mail.mail.MailService()
        insServ.smtpPortal.registerChecker(cred.checkers.AllowAnonymousAccess())
        domain = mail.maildir.MaildirDirdbmDomain(insServ, 'insertionDomain')
        insServ.domains['insertion.domain'] = domain
        insServ.portals['insertion.domain'] = cred.portal.Portal(domain)
        os.mkdir('insertionQueue')
        insServ.setQueue(mail.relaymanager.Queue('insertionQueue'))
        insServ.domains.setDefaultDomain(mail.relay.DomainQueuer(insServ))
        manager = mail.relaymanager.SmartHostSMTPRelayingManager(insServ.queue)
        manager.fArgs += ('test.identity.hostname',)
        helper = mail.relaymanager.RelayStateHelper(manager, 1)
        # Yoink!  Now the internet obeys OUR every whim!
        manager.mxcalc = mail.relaymanager.MXCalculator(self.resolver)
        # And this is our whim.
        self.auth.addresses['destination.domain'] = ['localhost']
        
        f = insServ.getSMTPFactory()
        self.insServer = reactor.listenTCP(0, f, interface='127.0.0.1')
        
        # Here is the service the previous one will connect to for final
        # delivery
        destServ = mail.mail.MailService()
        destServ.smtpPortal.registerChecker(cred.checkers.AllowAnonymousAccess())
        domain = mail.maildir.MaildirDirdbmDomain(destServ, 'destinationDomain')
        domain.addUser('user', 'password')
        destServ.domains['destination.domain'] = domain
        destServ.portals['destination.domain'] = cred.portal.Portal(domain)
        os.mkdir('destinationQueue')
        destServ.setQueue(mail.relaymanager.Queue('destinationQueue'))
        manager2 = mail.relaymanager.SmartHostSMTPRelayingManager(destServ.queue)
        helper = mail.relaymanager.RelayStateHelper(manager, 1)
        helper.startService()
        
        f = destServ.getSMTPFactory()
        self.destServer = reactor.listenTCP(0, f, interface='127.0.0.1')
        
        # Update the port number the *first* relay will connect to, because we can't use
        # port 25
        manager.PORT = self.destServer.getHost()[2]

        client = LineSendingProtocol([
            'HELO meson',
            'MAIL FROM: <user@wherever>',
            'RCPT TO: <user@destination.domain>',
            'DATA',
            'This is the message',
            '.',
            'QUIT'
        ])

        done = []
        f = protocol.ClientFactory()
        f.protocol = lambda: client
        f.clientConnectionLost = lambda *args: done.append(None)
        reactor.connectTCP('127.0.0.1', self.insServer.getHost()[2], f)
        
        i = 0
        while len(done) == 0 and i < 1000:
            reactor.iterate(0.01)
            i += 1
        
        self.failUnless(done)

        # First part of the delivery is done.  Poke the queue manually now
        # so we don't have to wait for the queue to be flushed.
        manager.checkState()

        for i in range(1000):
            reactor.iterate(0.01)
        
        mbox = domain.requestAvatar('user', None, pop3.IMailbox)[1]
        msg = mbox.getMessage(0).read()
        self.failIfEqual(msg.find('This is the message'), -1)
        
        self.insServer.stopListening()
        self.destServer.stopListening()
        helper.stopService()

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
        unittest.deferredResult(msg.eomReceived())
        
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
        unittest.deferredResult(m.eomReceived())
        
        lines = file(tmpfile).readlines()
        self.assertEquals([L[:-1] for L in lines], self.lines)

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

    def tearDown(self):
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

    def testProcessAlias(self):
        path = util.sibpath(__file__, 'process.alias.sh')
        a = mail.alias.ProcessAlias(path, None, None)
        m = a.createMessageReceiver()
        
        for l in self.lines:
            m.lineReceived(l)
        unittest.deferredResult(m.eomReceived())
        
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
        p = reactor.spawnProcess(protocol.ProcessProtocol(), "process_reader.py")
        expected = map(str, [
            mail.alias.AddressAlias('user1', None, None),
            mail.alias.MessageWrapper(p, 'echo'),
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
            mail.alias.MessageWrapper(p, 'echo'),
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
        
        p = reactor.spawnProcess(protocol.ProcessProtocol(), "process_reader.py")
        r = map(str, A4.resolve(aliases).objs)
        r.sort()
        expected = map(str, [
            mail.alias.MessageWrapper(p, 'echo')
        ])
        self.assertEquals(r, expected)
        reactor.iterate()
        reactor.iterate()
        reactor.iterate()

if not components.implements(reactor, interfaces.IReactorProcess):
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
