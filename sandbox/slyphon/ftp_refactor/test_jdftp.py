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
#
# written and maintained by slyphon (Jonathan D. Simms)

from __future__ import  nested_scopes

import sys, types, os.path, re
from StringIO import StringIO

from twisted import internet
from twisted.trial import unittest
from twisted.protocols import basic
from twisted.internet import reactor, protocol, defer
from twisted.cred import error, portal, checkers, credentials
from twisted.python import log

import jdftp as ftp
import jdftp
from jdftp import DTPFactory
from twisted.protocols.ftp import FTPClient

class NonClosingStringIO(StringIO):
    def close(self):
        pass

class CustomLogObserver(log.FileLogObserver):
    '''a log observer that prints more than the default'''
    def emit(self, eventDict):
       pass

# taken from t.test.test_pb
class IOPump:
    """Utility to pump data between clients and servers for protocol testing.

    Perhaps this is a utility worthy of being in protocol.py?
    """
    def __init__(self, client, server, clientIO, serverIO):
        self.client = client
        self.server = server
        self.clientIO = clientIO
        self.serverIO = serverIO

    def flush(self):
        "Pump until there is no more input or output."
        reactor.iterate()
        while self.pump():
            reactor.iterate()
        reactor.iterate()

    def pumpAndCount(self):
        numMessages = 0
        while True:
            result = self.pump()
            if result == 0:
                return numMessages
            else:
                numMessages += result
       
    def pump(self):
        """Move data back and forth.

        Returns whether any data was moved.
        """
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        cData = self.clientIO.read()
        sData = self.serverIO.read()
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        self.clientIO.truncate()
        self.serverIO.truncate()
        self.client.transport._checkProducer()
        self.server.transport._checkProducer()
        for byte in cData:
            self.server.dataReceived(byte)
        for byte in sData:
                self.client.dataReceived(byte)
        if cData or sData:
            return 1
        else:
            return 0
    
    def getTuple(self):
        return (self.client, self.server, self.pump, self.flush)

class ConnectedServerAndClient(object):
    dc   = None
    dp   = None
    ds   = None
    c    = None
    s    = None
    pump = None
    def __init__(self):
        """Returns a 3-tuple: (client, server, pump)
        """
        self.createPIClientAndServer()

    def createPIClientAndServer(self):
        svr = ftp.FTPFactory()
        svr.timeOut = None
        svr.dtpTimeout = None
        port = portal.Portal(ftp.FTPRealm())
        port.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
        svr.portal = port
        s = svr.buildProtocol(('127.0.0.1',))
        class Foo(basic.LineReceiver):
            def connectionMade(self):
                self.f = self.factory   # to save typing in pdb :-)
            def lineReceived(self,line):
                self.factory.lines.append(line)
        cf = protocol.ClientFactory()
        cf.protocol = Foo
        cf.lines = []
        c = cf.buildProtocol(('127.0.0.1',))
        self.cio = NonClosingStringIO()
        self.sio = NonClosingStringIO()
        c.makeConnection(protocol.FileWrapper(self.cio))
        s.makeConnection(protocol.FileWrapper(self.sio))
        pump = IOPump(c, s, self.cio, self.sio)
        self.c, self.s, self.pump = c, s, pump

    def getCSPumpTuple(self):
        return (self.c, self.s, self.pump)

    def getDtpCSPumpTuple(self):
        if not self.dc:
            self.connectDTPClient()
        return (self.dc, self.ds, self.dp)

class TestAnonymousAvatar(unittest.TestCase):
    def setUp(self):
        self.X = ConnectedServerAndClient()

    def tearDown(self):
        delayeds = reactor.getDelayedCalls()
        for d in delayeds:
            d.cancel()

    def testAnonymousLogin(self):
        c, s, pump = self.X.getCSPumpTuple()
        pump.flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.WELCOME_MSG])
        c.sendLine('USER anonymous')
        pump.flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.GUEST_NAME_OK_NEED_EMAIL])
        c.sendLine('PASS w00t@twistedmatrix.com')
        pump.flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.GUEST_LOGGED_IN_PROCEED], c.f.lines)


    def doAnonymousLogin(self,c,s,pump):
        c, s, pump = self.X.getCSPumpTuple()
        pump.flush()
        c.sendLine('USER anonymous')
        pump.flush()
        c.sendLine('PASS w00t@twistedmatrix.com')
        pump.flush()


    def testPWDOnLogin(self):
        c, s, pump = self.X.getCSPumpTuple()
        self.doAnonymousLogin(c,s,pump)
        c.sendLine('PWD')
        pump.flush()
        self.assertEquals(c.f.lines[-1], '257 "/" is current directory.')


    def testCWD(self):
        import warnings
        warnings.warn("""This test is VERY FRAGILE! in fact, its so fragile it won't run on any other computer but mine""")
        c, s, pump = self.X.getCSPumpTuple()
        send = c.sendLine
        flush = pump.flush

        self.doAnonymousLogin(c,s,pump)

        send('CWD src'); flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.REQ_FILE_ACTN_COMPLETED_OK])

        send('PWD'); flush()
        self.assertEquals(c.f.lines[-1], '257 "/src" is current directory.')

        send('CWD freemind'); flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.REQ_FILE_ACTN_COMPLETED_OK])

        send('PWD'); flush()
        self.assertEquals(c.f.lines[-1], '257 "/src/freemind" is current directory.')

        send('CWD ../radix'); flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.REQ_FILE_ACTN_COMPLETED_OK])

        send('PWD'); flush()
        send('CWD ../../../'); flush()


    def testCDUP(self):
        c, s, pump = self.X.getCSPumpTuple()
        send = c.sendLine
        flush = pump.flush

        self.doAnonymousLogin(c,s,pump)
        send('CWD src/freemind/doc'); flush()

        send('PWD'); flush()
        self.assertEquals(c.f.lines[-1], '257 "/src/freemind/doc" is current directory.')
    
        send('CDUP'); flush()
        send('PWD'); flush()
        self.assertEquals(c.f.lines[-1], '257 "/src/freemind" is current directory.')

        send('CDUP'); flush()
        send('PWD'); flush()
        self.assertEquals(c.f.lines[-1], '257 "/src" is current directory.')

        send('CDUP'); flush()
        send('PWD'); flush()
        self.assertEquals(c.f.lines[-1], '257 "/" is current directory.')


    def testWelcomeMessage(self):
        c, s, pump = self.X.getCSPumpTuple()
        pump.flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.WELCOME_MSG])

TestAnonymousAvatar.skip = 'skip until we can support it'


def getPortal():
    port = portal.Portal(ftp.FTPRealm())
    port.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
    return port

class ServerFactoryForTest(protocol.Factory):
    def __init__(self, portal):
        self.protocol = ftp.FTP
        self.allowAnonymous = True
        self.userAnonymous = 'anonymous'
        self.timeOut = 30
        self.dtpTimeout = 10
        self.maxProtocolInstances = 100
        self.instances = []
        self.portal = portal
    
class DummyClient(basic.LineReceiver):
    logname = None
    def __init__(self):
        self.lines = []
    def connectionMade(self):
        self.f = self.factory   # to save typing in pdb :-)
    def lineReceived(self,line):
        log.debug('DummyClient %s received line: %s' % (self.logname,line))
        self.lines.append(line)

class ConnectedFTPServer(object):
    c    = None
    s    = None
    iop  = None
    dc   = None
    ds   = None
    diop = None
    
    def __init__(self):
        self.deferred = defer.Deferred()
        s = ftp.FTP()
        c = DummyClient()
        c.logname = 'ftp-pi'
        self.cio, self.sio = NonClosingStringIO(), NonClosingStringIO()
        s.factory = ServerFactoryForTest(getPortal())
        s.factory.timeOut = None
        s.factory.dtpTimeout = None

        c.factory = protocol.ClientFactory()
        c.factory.protocol = DummyClient

        c.makeConnection(protocol.FileWrapper(self.cio))
        s.makeConnection(protocol.FileWrapper(self.sio))

        iop = IOPump(c, s, self.cio, self.sio)
        self.c, self.s, self.iop = c, s, iop

    def hookUpDTP(self):
        log.debug('hooking up dtp')
        self.dcio, self.dsio = NonClosingStringIO(), NonClosingStringIO()

        ds = ftp.DTP()
        ds.pi = self.s
        ds.pi.dtpInstance = ds
        ds.pi.dtpPort = ('i','',0)

        ds.factory = ftp.DTPFactory(self.s)
        self.s.dtpFactory = ds.factory

        self.s.TestingSoJustSkipTheReactorStep = True

        ds.makeConnection(protocol.FileWrapper(self.dsio))
        
        dc = DummyClient()
        dc.logname = 'ftp-dtp'
        dc.factory = protocol.ClientFactory()
        dc.factory.protocol = DummyClient
        dc.makeConnection(protocol.FileWrapper(self.dcio))

        iop = IOPump(dc, ds, self.dcio, self.dsio)
        self.dc, self.ds, self.diop = dc, ds, iop
        log.debug('flushing pi buffer')
        self.iop.flush()
        log.debug('hooked up dtp')
        d, self.deferred = self.deferred, defer.Deferred()
        d.callback(None)

    def getDtpCSTuple(self):
        if not self.s.shell:
            self.loadAvatar()

        if not self.dc:
            self.hookUpDTP()
        return (self.dc, self.ds, self.diop)

    def getCSTuple(self):
        return (self.c, self.s, self.iop, self.srvReceive)

    def srvReceive(self, *args):
        for msg in args:
            self.s.lineReceived(msg)
            self.iop.flush()

    def loadAvatar(self):
        log.debug('BogusAvatar.loadAvatar')
        shell = BogusAvatar()
        shell.tld = '/home/foo'
        shell.debug = True
        shell.clientwd = '/'
        shell.user = 'anonymous'
        shell.uid = 1000
        shell.gid = 1000
        self.s.shell = shell
        self.s.user = 'anonymous'


bogusfiles = [
{'type': 'f',
 'name': 'foo.txt', 
 'size': 1586, 
 'date': '20030102125902',
 'listrep': '-rwxr-xr-x 1 anonymous anonymous 1586 Jan 02 12:59 foo.txt\r\n'
},
{'type': 'f',
 'name': 'bar.tar.gz',
 'size': 4872,
 'date': '2003 11 22 01 55 22',
 'listrep': '-rwxr-xr-x 1 anonymous anonymous 4872 Nov 22 01:55 bar.tar.gz\r\n'
} ]

bogusDirs = {
 'name': '/home/foo',
 'subdirs': 
        [ {'name': '/home/foo/dir1',
           'subdirs': []},  
          {'name': '/home/foo/dir2',
           'subdirs': []}
        ]
}

class BogusAvatar:
    __implements__ = (ftp.IFTPShell,)
    
    def __init__(self):
        self.user     = None        # user name
        self.uid      = None        # uid of anonymous user for shell
        self.gid      = None        # gid of anonymous user for shell
        self.clientwd = None
        self.tld      = None
        self.debug    = True 

    def pwd(self):
        pass

    def cwd(self, path):
        pass

    def cdup(self):
        pass

    def dele(self, path):
        pass

    def mkd(self, path):
        pass

    def rmd(self, path):
        pass

    def retr(self, path):
        log.debug('BogusAvatar.retr')
        text = ['f' for n in xrange(bogusfiles[0]['size'])]
        sio = StringIO(''.join(text))
        log.debug('BogusAvatar.retr: about to return: %s' % sio.getvalue())
        sio.seek(0)
        return (sio, len(sio.getvalue()))

    def stor(self, params):
        pass

    def list(self, path):
        sio = NonClosingStringIO()
        for f in bogusfiles:
            sio.write(f['listrep'])
        sio.seek(0)
        return (sio, len(sio.getvalue()))

    def mdtm(self, path):
        pass

    def size(self, path):
        pass

    def nlist(self, path):
        pass


        
class TestFTPServer(unittest.TestCase):
    def setUp(self):
        self.cnx = ConnectedFTPServer()
        
    def tearDown(self):
        delayeds = reactor.getDelayedCalls()
        for d in delayeds:
            d.cancel()
        del self.cnx

    def testNotLoggedInReply(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        cmdlist = ['CDUP', 'CWD', 'LIST', 'MODE', 'PASV', 'PORT', 
                 'PWD', 'RETR', 'STRU', 'SYST', 'TYPE']
        for cmd in cmdlist:
            send(cmd)
            self.failUnless(cli.lines > 0)
            self.assertEqual(cli.lines[-1], ftp.RESPONSE[ftp.NOT_LOGGED_IN])

    def testBadCmdSequenceReply(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        send = self.cnx.srvReceive
        send('PASS') 
        self.failUnless(cli.lines > 0)
        self.assertEqual(cli.lines[-1], 
                ftp.RESPONSE[ftp.BAD_CMD_SEQ] % 'USER required before PASS')

    def testBadCmdSequenceReplyPartTwo(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        self.cnx.loadAvatar()
        self.failUnlessRaises(ftp.BadCmdSequenceError, self.cnx.s.ftp_RETR,'foo')
        #self.assertEqual(cli.lines[-1], ftp.RESPONSE[ftp.BAD_CMD_SEQ] % 'must send PORT or PASV before RETR')
        log.flushErrors(ftp.BadCmdSequenceError)

    def testCmdNotImplementedForArgErrors(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        self.cnx.loadAvatar()
        self.failUnlessRaises(ftp.CmdNotImplementedForArgError, self.cnx.s.ftp_MODE, 'z')
        self.failUnlessRaises(ftp.CmdNotImplementedForArgError, self.cnx.s.ftp_STRU, 'I')

    def testDecodeHostPort(self):
        self.assertEquals(self.cnx.s.decodeHostPort('25,234,129,22,100,23'), 
                ('25.234.129.22', 25623))

    def testPASV(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        self.cnx.loadAvatar()
        self.cnx.s.ftp_PASV()
        iop.flush()
        reply = cli.lines[-1]
        self.assert_(re.search(r'227 =.*,[0-2]?[0-9]?[0-9],[0-2]?[0-9]?[0-9]',cli.lines[-1]))


    def testTYPE(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        self.cnx.loadAvatar()
        for n in ['I', 'A', 'L', 'i', 'a', 'l']:
            self.cnx.s.ftp_TYPE(n)
            iop.flush()
            self.assertEquals(cli.lines[-1], ftp.RESPONSE[ftp.TYPE_SET_OK] % n.upper())
            if n in ['I', 'L', 'i', 'l']:
                self.assertEquals(self.cnx.s.binary, True)
            else:
                self.assertEquals(self.cnx.s.binary, False)
        s = ftp.FTP()
        okParams = ['i', 'a', 'l']
        for n in [chr(x) for x in xrange(97,123)]:
            if n not in okParams:
                self.failUnlessRaises(ftp.CmdArgSyntaxError, s.ftp_TYPE, n)           
        self.cnx.hookUpDTP()
        dc, ds, diop = self.cnx.getDtpCSTuple()
        sr.dtpTxfrMode = ftp.PASV
        iop.flush()
        diop.flush()
        log.debug('flushed buffers, about to run RETR')
        sr.ftp_RETR('/home/foo/foo.txt')
        iop.flush()
        diop.flush()
        log.debug(dc.lines)
        #self.assert_(len(dc.lines) >= 1)
        self.assert_(ds.transport.closed)

    testTYPE.todo = 'need to test for /r/n'

    def testRETR(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        iop.flush()

        self.cnx.loadAvatar()
        self.cnx.s.ftp_PASV()
        log.debug('ran ftp.PASV')
        iop.flush()
        
        #print ('log is %s' % log)
        self.cnx.deferred.addCallback(lambda _:self._continueTestRETR)
        self.cnx.hookUpDTP()

    def _continueTestRETR(self): 
        print ('_continueTestRETR')
        dc, ds, diop = self.cnx.getDtpCSTuple()
        self.assert_(self.cnx.s.blocked is None)
        self.assert_(self.cnx.s.dtpTxfrMode == ftp.PASV)
        self.assert_(self.cnx.ds.transport.closed is False)
        self.assert_(self.cnx.ds.transport.connected is True)
        self.assert_(self.cnx.dc.transport.closed is False)
        self.assert_(self.cnx.dc.transport.connected is True)

        self.cnx.ds.factory.deferred.addCallback(lambda _:self._finishTestRETR)
        print 'about to send RETR command'
        self.cnx.cio.send('RETR /home/foo/foo.txt')
        iop.flush()


    #def _finishTestRETR(self):
        diop.flush()
        self.assert_(len(dc.lines) > 1)
        print 'dc.lines: %s' % dc.lines
        self.assert_(ds.transport.closed)
 
        
    #testRETR.todo = 'not quite there yet'


    def testSYST(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        self.cnx.loadAvatar()
        self.cnx.s.ftp_SYST()
        iop.flush()
        self.assertEquals(cli.lines[-1], ftp.RESPONSE[ftp.NAME_SYS_TYPE])

    def testLIST(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        self.cnx.loadAvatar()
        self.cnx.hookUpDTP()
        dc, ds, diop = self.cnx.getDtpCSTuple()
        sr.ftp_LIST('/')
        iop.flush()
        diop.flush()
        self.assert_(len(dc.lines) > 1)
        log.debug('dc.lines: %s' % dc.lines)
        self.assert_(ds.transport.closed)
        testlist = [b['listrep'] for b in bogusfiles]
        for n in xrange(len(dc.lines)):
            self.assertEqual(testlist[n][:-1], dc.lines[n])

    testLIST.todo = "fix this one"


