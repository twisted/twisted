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
# Server tests written and maintained by slyphon (Jonathan D. Simms)
# Client tests written and maintained by spiv

from __future__ import  nested_scopes

import sys, types, os.path, re
from StringIO import StringIO

from twisted import internet
from twisted.trial import unittest
from twisted.protocols import basic
from twisted.internet import reactor, protocol, defer, interfaces
from twisted.cred import error, portal, checkers, credentials
from twisted.python import log, components

import jdftp as ftp
import jdftp
from jdftp import DTPFactory

class NonClosingStringIO(StringIO):
    def close(self):
        pass

class CustomFileWrapper(protocol.FileWrapper):
    def write(self, data):
        protocol.FileWrapper.write(self, data)
        #self._checkProducer()

    #def loseConnection(self):
        #self.closed = 1


class CustomLogObserver(log.FileLogObserver):
    '''a log observer that prints more than the default'''
    def emit(self, eventDict):
       pass


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

class TestAnonymousAvatar:#(unittest.TestCase):
    def setUp(self):
        self.cnx = ConnectedFTPServer()

    def tearDown(self):
        delayeds = reactor.getDelayedCalls()
        for d in delayeds:
            d.cancel()

    def testAnonymousLogin(self):
        c, s, pump = self.cnx.getCSPumpTuple()
        pump.flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.WELCOME_MSG])
        c.sendLine('USER anonymous')
        pump.flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.GUEST_NAME_OK_NEED_EMAIL])
        c.sendLine('PASS w00t@twistedmatrix.com')
        pump.flush()
        self.assertEquals(c.f.lines[-1], ftp.RESPONSE[ftp.GUEST_LOGGED_IN_PROCEED], c.f.lines)


    def doAnonymousLogin(self,c,s,pump):
        c, s, pump = self.cnx.getCSPumpTuple()
        pump.flush()
        c.sendLine('USER anonymous')
        pump.flush()
        c.sendLine('PASS w00t@twistedmatrix.com')
        pump.flush()


    def testPWDOnLogin(self):
        c, s, pump = self.cnx.getCSPumpTuple()
        self.doAnonymousLogin(c,s,pump)
        c.sendLine('PWD')
        pump.flush()
        self.assertEquals(c.f.lines[-1], '257 "/" is current directory.')


    def testCWD(self):
        import warnings
        warnings.warn("""This test is VERY FRAGILE! in fact, its so fragile it won't run on any other computer but mine""")
        c, s, pump = self.cnx.getCSPumpTuple()
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
        c, s, pump = self.cnx.getCSPumpTuple()
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
        c, s, pump = self.cnx.getCSPumpTuple()
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
    
class Dummy(basic.LineReceiver):
    logname = None
    def __init__(self):
        self.lines = []
        self.rawData = []
    def connectionMade(self):
        self.f = self.factory   # to save typing in pdb :-)
    def lineReceived(self,line):
        self.lines.append(line)
    def rawDataReceived(self, data):
        self.rawData.append(data)
    def lineLengthExceeded(self, line):
        pass

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
        c = Dummy()
        c.logname = 'ftp-pi'
        self.cio, self.sio = NonClosingStringIO(), NonClosingStringIO()
        s.factory = ServerFactoryForTest(getPortal())
        s.factory.timeOut = None
        s.factory.dtpTimeout = None

        c.factory = protocol.ClientFactory()
        c.factory.protocol = Dummy

        c.makeConnection(CustomFileWrapper(self.cio))
        s.makeConnection(CustomFileWrapper(self.sio))

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

        ds.makeConnection(CustomFileWrapper(self.dsio))
        
        dc = Dummy()
        dc.logname = 'ftp-dtp'
        dc.factory = protocol.ClientFactory()
        dc.factory.protocol = Dummy
        dc.setRawMode()
        del dc.lines
        dc.makeConnection(CustomFileWrapper(self.dcio))

        iop = IOPump(dc, ds, self.dcio, self.dsio)
        self.dc, self.ds, self.diop = dc, ds, iop
        log.debug('flushing pi buffer')
        self.iop.flush()
        log.debug('hooked up dtp')
        return

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
        return shell


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

class BogusAvatar(object):
    __implements__ = (ftp.IFTPShell,)

    filesize = None
    
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

    def retr(self, path=None):
        log.debug('BogusAvatar.retr')

        if path == 'ASCII':
            text = """this is a line with a dos terminator\r\n
this is a line with a unix terminator\n"""
        else:
            self.path = path
            
            if self.filesize is not None:   # self.filesize is used in the sanity check
                size = self.filesize
            else:
                size = bogusfiles[0]['size']

            endln = ['\r','\n']
            text = []
            for n in xrange(size/26):
                line = [chr(x) for x in xrange(97,123)]
                line.extend(endln)
                text.extend(line)
            
            del text[(size - 2):]
            text.extend(endln)
        
        sio = NonClosingStringIO(''.join(text))
        self.finalFileSize = len(sio.getvalue())
        log.msg("BogusAvatar.retr: file size = %d" % self.finalFileSize)
        sio.seek(0)
        self.sentfile = sio
        return (sio, self.finalFileSize)

    def stor(self, params):
        pass

    def list(self, path):
        sio = NonClosingStringIO()
        for f in bogusfiles:
            sio.write(f['listrep'])
        sio.seek(0)
        self.sentlist = sio
        return (sio, len(sio.getvalue()))

    def mdtm(self, path):
        pass

    def size(self, path):
        pass

    def nlist(self, path):
        pass

class FTPTestCase(unittest.TestCase):
    def setUp(self):
        self.cnx = ConnectedFTPServer()
        
    def tearDown(self):
        delayeds = reactor.getDelayedCalls()
        for d in delayeds:
            d.cancel()
        self.cnx = None

class TestUtilityFunctions(unittest.TestCase):
    def testCleanPath(self):
        evil_paths = [r"..\/*/foobar/ding//dong/\\**"]
        for ep in evil_paths:
            log.msg(ftp.cleanPath(ep))
        self.fail('this test needs more work')

TestUtilityFunctions.todo = 'workin on it'
    

class TestFTPFactory(FTPTestCase):
    def testBuildProtocol(self):
        ftpf = ftp.FTPFactory()
        cinum = ftpf.currentInstanceNum
        p = ftpf.buildProtocol(('i', None, 30000))
        self.failUnless(components.implements(ftpf, interfaces.IProtocolFactory), 
                "FTPFactory does not implement interfaces.IProtocolFactory")
        self.failUnless(components.implements(p, interfaces.IProtocol),
                "protocol instance does not implement interfaces.IProtocol")

        self.failUnlessEqual(p.protocol, ftpf.protocol)
        self.failUnlessEqual(p.protocol, ftp.FTP)

        self.failUnlessEqual(p.portal, ftpf.portal)
        self.failUnlessEqual(p.timeOut, ftp.FTPFactory.timeOut)
        self.failUnlessEqual(p.factory, ftpf)

        self.failUnlessEqual(ftpf.currentInstanceNum, cinum + 1)
        self.failUnlessEqual(p.instanceNum, ftpf.currentInstanceNum)
        self.failUnlessEqual(len(ftpf.instances), 1)
        self.failUnlessEqual(ftpf.instances[0], p)
        
class TestFTPServer(FTPTestCase):
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

        sr.ftp_TYPE('A')        # set ascii mode
        self.assertEquals(self.cnx.s.binary, False)

        iop.flush()
        diop.flush()
        log.debug('flushed buffers, about to run RETR')
        sr.ftp_RETR('ASCII')
        iop.flush()
        diop.flush()
        self.failUnless(len(dc.rawData) >= 1)
        log.msg(dc.rawData)
        rx = ''.join(dc.rawData)
        log.msg(rx)
        self.failUnlessEqual(rx.count('\r\n'), 2, "more than 2 \\r\\n's ")
        self.fail('test is not complete')

    testTYPE.todo = 'rework tests to make sure only binary is supported'

    def testRETR(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        avatar = self.cnx.loadAvatar()

        sr.ftp_TYPE('L')
        self.assert_(self.cnx.s.binary == True)

        iop.flush()
        self.cnx.hookUpDTP()
        dc, ds, diop = self.cnx.getDtpCSTuple()
        sr.dtpTxfrMode = ftp.PASV
        self.assert_(sr.blocked is None)
        self.assert_(sr.dtpTxfrMode == ftp.PASV)
        log.msg('about to send RETR command')
        
        filename = '/home/foo/foo.txt'
        
        send('RETR %s' % filename)
        iop.flush()
        diop.flush()
        log.msg('dc.rawData: %s' % dc.rawData)
        self.assert_(len(dc.rawData) >= 1)
        self.failUnlessEqual(avatar.path, filename)
        rx = ''.join(dc.rawData)
        self.failUnlessEqual(rx, avatar.sentfile.getvalue())
        
    #testRETR.todo = 'not quite there yet'

    def testSYST(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        self.cnx.loadAvatar()
        self.cnx.s.ftp_SYST()
        iop.flush()
        self.assertEquals(cli.lines[-1], ftp.RESPONSE[ftp.NAME_SYS_TYPE])


    def testLIST(self):
        cli, sr, iop, send = self.cnx.getCSTuple()
        avatar = self.cnx.loadAvatar()
        sr.dtpTxfrMode = ftp.PASV 
        self.cnx.hookUpDTP()
        dc, ds, diop = self.cnx.getDtpCSTuple()
        self.assert_(hasattr(self.cnx.s, 'binary'))
        self.cnx.s.binary = True
        sr.ftp_LIST('/')
        iop.flush()
        diop.flush()
        log.debug('dc.rawData: %s' % dc.rawData)
        self.assert_(len(dc.rawData) > 1)
        avatarsent = avatar.sentlist.getvalue()
        dcrx = ''.join(dc.rawData)
        #print avatarsent.strip(), dcrx.strip()
        self.assertEqual(avatarsent, dcrx, 
"""
avatar's sentlist != dtp client's ''.join(rawData)

avatar's sentlist:

%s

''.join(dc.rawData):

%s
""" % (avatarsent, dcrx))

    
    #testLIST.todo = 'something is b0rK3n'

class TestDTPTesting(FTPTestCase):
    def testDTPTestingSanityCheck(self):
        filesizes = [(n*100) for n in xrange(100,110)]
        for fs in filesizes:
            self.tearDown()
            self.setUp()
            self.runtest(fs)

    def runtest(self, filesize):
        cli, sr, iop, send = self.cnx.getCSTuple()
        avatar = self.cnx.loadAvatar()
        avatar.filesize = filesize
        sr.dtpTxfrMode = ftp.PASV
        sr.binary = True                            # set transfer mode to binary
        self.cnx.hookUpDTP()
        dc, ds, diop = self.cnx.getDtpCSTuple()
        sr.ftp_RETR('')
        iop.flush()
        diop.flush()
        log.debug('dc.rawData size: %d' % len(dc.rawData))
        rxLines = ''.join(dc.rawData)
        lenRxLines = len(rxLines)
        sizes = 'filesize before txmit: %d, filesize after txmit: %d' % (avatar.finalFileSize, lenRxLines)
        percent = 'percent actually received %f' % ((float(lenRxLines) / float(avatar.finalFileSize))*100)
        log.debug(sizes)
        log.debug(percent)
        self.assertEquals(lenRxLines, avatar.finalFileSize)


# --- Client Tests -------------------------------------------




class ConnectedFTPClient(object):
    c    = None
    s    = None
    iop  = None
    dc   = None
    ds   = None
    diop = None

    def __init__(self):
        self.deferred = defer.Deferred()
        s = Dummy()
        c = ftp.FTPClient()

        self.cio, self.sio = NonClosingStringIO(), NonClosingStringIO()
        s.factory = protocol.ServerFactory()

        c.factory = protocol.ClientFactory()
        c.factory.maxProtocolInstances = 100000
        c.factory.protocol = ftp.FTPClient

        c.makeConnection(CustomFileWrapper(self.cio))
        s.makeConnection(CustomFileWrapper(self.sio))

        iop = IOPump(c, s, self.cio, self.sio)
        self.c, self.s, self.iop = c, s, iop

    def hookUpDTP(self):
        raise NotImplementedException("don't do that, we're not ready")
        log.debug('hooking up dtp')
        self.dcio, self.dsio = NonClosingStringIO(), NonClosingStringIO()

        ds = Dummy()
        ds.pi = self.s

        ds.factory = protocol.ServerFactory()
        self.s.dtpFactory = ds.factory

        ds.makeConnection(CustomFileWrapper(self.dsio))
        
        dc = DTP()
        dc.logname = 'ftp-dtp'
        dc.factory = protocol.ClientFactory()
        dc.factory.protocol = Dummy
        dc.setRawMode()
        del dc.lines
        dc.makeConnection(CustomFileWrapper(self.dcio))

        iop = IOPump(dc, ds, self.dcio, self.dsio)
        self.dc, self.ds, self.diop = dc, ds, iop
        log.debug('flushing pi buffer')
        self.iop.flush()
        log.debug('hooked up dtp')
        return

    def getCSTuple(self):
        return (self.c, self.s, self.iop)


class FTPClientTestCase(unittest.TestCase):
    def setUp(self):
        self.cnx = ConnectedFTPClient()

    def tearDown(self):
        delayeds = reactor.getDelayedCalls()
        for d in delayeds:
            d.cancel()
        self.cnx = None
 

class TestFTPClient:#(FTPClientTestCase):
    def testSanity(self):
        pass

    def testSendLine(self):
        # more of a sanity check
        c, s, iop = self.cnx.getCSTuple()
        c.sendLine('test')
        iop.flush()
        self.assertEquals(s.lines[-1], 'test')
    
    


