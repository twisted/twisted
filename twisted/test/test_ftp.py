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

"""FTP tests.

Server Test Maintainer: slyphon (Jonathan D. Simms)
Client Test Maintainer: spiv

"""

from __future__ import  nested_scopes

import sys, types, os.path, re
from StringIO import StringIO

from twisted import internet
from twisted.trial import unittest
from twisted.protocols import basic
from twisted.internet import reactor, protocol, defer, interfaces
from twisted.cred import error, portal, checkers, credentials
from twisted.python import log, components, failure

from twisted.protocols import ftp, loopback

class NonClosingStringIO(StringIO):
    def close(self):
        pass

StringIOWithoutClosing = NonClosingStringIO


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
        import os.path as osp
        evilPaths = [r"..\/*/foobar/ding//dong/\\**", 
        r"../../\\**/*/fhet/*/..///\\//..///#$#221./*"]
        exorcisedPaths = ["..\/foobar/ding/dong","../../../#$#221."]
        for i in range(len(evilPaths)):
            cp = ftp.cleanPath(evilPaths[i])
            self.failUnlessEqual(cp, exorcisedPaths[i])
            log.msg(cp)

    testCleanPath.skip = 'this test needs more work'

class TestFTPFactory(FTPTestCase):
    def testBuildProtocol(self):
        ftpf = ftp.FTPFactory(maxProtocolInstances=1)
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

    testBuildProtocol.skip = "add test for maxProtocolInstances=None"
        
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

    testTYPE.skip = 'rework tests to make sure only binary is supported'

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
        
    testRETR.skip = 'awaiting MASSIVE refactoring of ftp.py'

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


class TestAnonymousAvatar(FTPTestCase):
    def testAnonymousLogin(self):
        c, s, pump, send = self.cnx.getCSTuple()

        pump.flush()
        got = c.lines[-2:]
        wanted = ftp.RESPONSE[ftp.WELCOME_MSG].split('\r\n')
        self.assertEquals(wanted, got, "wanted: %s\n\ngot: %s" % (wanted,got))

        c.sendLine('USER anonymous')
        pump.flush()
        self.assertEquals(c.lines[-1], ftp.RESPONSE[ftp.GUEST_NAME_OK_NEED_EMAIL])

        c.sendLine('PASS w00t@twistedmatrix.com')
        pump.flush()
        wanted = ftp.RESPONSE[ftp.GUEST_LOGGED_IN_PROCEED]
        got = c.lines[-1]
        self.assertEquals(wanted, got, "wanted: %s\n\ngot: %s" % (wanted,got))

    testAnonymousLogin.skip = 'this test needs to be refactored' 
    
    def doAnonymousLogin(self,c,s,pump):
        c, s, pump, send = self.cnx.getCSTuple()
        pump.flush()
        c.sendLine('USER anonymous')
        pump.flush()
        c.sendLine('PASS w00t@twistedmatrix.com')
        pump.flush()


    def testPWDOnLogin(self):
        c, s, pump, send = self.cnx.getCSTuple()
        self.doAnonymousLogin(c,s,pump)
        c.sendLine('PWD')
        pump.flush()
        self.assertEquals(c.lines[-1], '257 "/" is current directory.')

    testPWDOnLogin.skip = 'need to implement fake filesystem for testing' 

    def testCWD(self):
        import warnings
        warnings.warn("""This test is VERY FRAGILE! in fact, its so fragile it won't run on any other computer but mine""")
        c, s, pump, send = self.cnx.getCSTuple()
        send = c.sendLine
        flush = pump.flush

        self.doAnonymousLogin(c,s,pump)

        send('CWD src'); flush()
        self.assertEquals(c.lines[-1], ftp.RESPONSE[ftp.REQ_FILE_ACTN_COMPLETED_OK])

        send('PWD'); flush()
        self.assertEquals(c.lines[-1], '257 "/src" is current directory.')

        send('CWD freemind'); flush()
        self.assertEquals(c.lines[-1], ftp.RESPONSE[ftp.REQ_FILE_ACTN_COMPLETED_OK])

        send('PWD'); flush()
        self.assertEquals(c.lines[-1], '257 "/src/freemind" is current directory.')

        send('CWD ../radix'); flush()
        self.assertEquals(c.lines[-1], ftp.RESPONSE[ftp.REQ_FILE_ACTN_COMPLETED_OK])

        send('PWD'); flush()
        send('CWD ../../../'); flush()

    testCWD.skip = 'need to implement fake filesystem for testing' 


    def testCDUP(self):
        c, s, pump, send = self.cnx.getCSTuple()
        send = c.sendLine
        flush = pump.flush

        self.doAnonymousLogin(c,s,pump)
        send('CWD src/freemind/doc'); flush()

        send('PWD'); flush()
        self.assertEquals(c.lines[-1], '257 "/src/freemind/doc" is current directory.')
    
        send('CDUP'); flush()
        send('PWD'); flush()
        self.assertEquals(c.lines[-1], '257 "/src/freemind" is current directory.')

        send('CDUP'); flush()
        send('PWD'); flush()
        self.assertEquals(c.lines[-1], '257 "/src" is current directory.')

        send('CDUP'); flush()
        send('PWD'); flush()
        self.assertEquals(c.lines[-1], '257 "/" is current directory.')

    testCDUP.skip = 'need to implement fake filesystem for testing' 

#    def testWelcomeMessage(self):
#        c, s, pump, send = self.cnx.getCSTuple()
#        pump.flush()
#        self.assertEquals(c.lines[-1], ftp.RESPONSE[ftp.WELCOME_MSG])
#
#    testWelcomeMessage.todo = 'not ready yet'

    def testGetUserUIDAndGID(self):
        pass

#TestAnonymousAvatar.skip = 'skip until we can support it'


# -- Experimenting with process protocol

class ChildProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, doneLoading):
        self.doneLoading = doneLoading

    def outReceived(self, data):
        if 'set uid/gid' in data:
            self.doneLoading.callback("twistd ready")

    def errReceived(self, data):
        self.doneLoading.errback(data)

    def processEnded(self, status):
        self.doneLoading.callback("It's done")


# -- Client Tests -----------------------------------------------------------


class PrintLines(protocol.Protocol):
    """Helper class used by FTPFileListingTests."""

    def __init__(self, lines):
        self._lines = lines

    def connectionMade(self):
        for line in self._lines:
            self.transport.write(line + "\r\n")
        self.transport.loseConnection()

class MyFTPFileListProtocol(ftp.FTPFileListProtocol):
    def __init__(self):
        self.other = []
        ftp.FTPFileListProtocol.__init__(self)

    def unknownLine(self, line):
        self.other.append(line)

class FTPFileListingTests(unittest.TestCase):
    def getFilesForLines(self, lines):
        fileList = MyFTPFileListProtocol()
        loopback.loopback(PrintLines(lines), fileList)
        return fileList.files, fileList.other

    def testOneLine(self):
        # This example line taken from the docstring for FTPFileListProtocol
        line = '-rw-r--r--   1 root     other        531 Jan 29 03:26 README'
        (file,), other = self.getFilesForLines([line])
        self.failIf(other, 'unexpect unparsable lines: %s' % repr(other))
        self.failUnless(file['filetype'] == '-', 'misparsed fileitem')
        self.failUnless(file['perms'] == 'rw-r--r--', 'misparsed perms')
        self.failUnless(file['owner'] == 'root', 'misparsed fileitem')
        self.failUnless(file['group'] == 'other', 'misparsed fileitem')
        self.failUnless(file['size'] == 531, 'misparsed fileitem')
        self.failUnless(file['date'] == 'Jan 29 03:26', 'misparsed fileitem')
        self.failUnless(file['filename'] == 'README', 'misparsed fileitem')
        self.failUnless(file['nlinks'] == 1, 'misparsed nlinks')
        self.failIf(file['linktarget'], 'misparsed linktarget')

    def testVariantLines(self):
        line1 = 'drw-r--r--   2 root     other        531 Jan  9  2003 A'
        line2 = 'lrw-r--r--   1 root     other          1 Jan 29 03:26 B -> A'
        line3 = 'woohoo! '
        (file1, file2), (other,) = self.getFilesForLines([line1, line2, line3])
        self.failUnless(other == 'woohoo! \r', 'incorrect other line')
        # file 1
        self.failUnless(file1['filetype'] == 'd', 'misparsed fileitem')
        self.failUnless(file1['perms'] == 'rw-r--r--', 'misparsed perms')
        self.failUnless(file1['owner'] == 'root', 'misparsed owner')
        self.failUnless(file1['group'] == 'other', 'misparsed group')
        self.failUnless(file1['size'] == 531, 'misparsed size')
        self.failUnless(file1['date'] == 'Jan  9  2003', 'misparsed date')
        self.failUnless(file1['filename'] == 'A', 'misparsed filename')
        self.failUnless(file1['nlinks'] == 2, 'misparsed nlinks')
        self.failIf(file1['linktarget'], 'misparsed linktarget')
        # file 2
        self.failUnless(file2['filetype'] == 'l', 'misparsed fileitem')
        self.failUnless(file2['perms'] == 'rw-r--r--', 'misparsed perms')
        self.failUnless(file2['owner'] == 'root', 'misparsed owner')
        self.failUnless(file2['group'] == 'other', 'misparsed group')
        self.failUnless(file2['size'] == 1, 'misparsed size')
        self.failUnless(file2['date'] == 'Jan 29 03:26', 'misparsed date')
        self.failUnless(file2['filename'] == 'B', 'misparsed filename')
        self.failUnless(file2['nlinks'] == 1, 'misparsed nlinks')
        self.failUnless(file2['linktarget'] == 'A', 'misparsed linktarget')

    def testUnknownLine(self):
        files, others = self.getFilesForLines(['ABC', 'not a file'])
        self.failIf(files, 'unexpected file entries')
        self.failUnless(others == ['ABC\r', 'not a file\r'],
                        'incorrect unparsable lines: %s' % repr(others))

    def testYear(self):
        # This example derived from bug description in issue 514.
        fileList = ftp.FTPFileListProtocol()
        class PrintLine(protocol.Protocol):
            def connectionMade(self):
                self.transport.write('-rw-r--r--   1 root     other        531 Jan 29 2003 README\n')
                self.transport.loseConnection()
        loopback.loopback(PrintLine(), fileList)
        file = fileList.files[0]
        self.failUnless(file['size'] == 531, 'misparsed fileitem')
        self.failUnless(file['date'] == 'Jan 29 2003', 'misparsed fileitem')
        self.failUnless(file['filename'] == 'README', 'misparsed fileitem')

class FTPClientTests(unittest.TestCase):
    def testFailedRETR(self):
        try:
            f = protocol.Factory()
            f.noisy = 0
            f.protocol = protocol.Protocol
            port = reactor.listenTCP(0, f, interface="127.0.0.1")
            n = port.getHost()[2]
            # This test data derived from a bug report by ranty on #twisted
            responses = ['220 ready, dude (vsFTPd 1.0.0: beat me, break me)',
                         # USER anonymous
                         '331 Please specify the password.',
                         # PASS twisted@twistedmatrix.com
                         '230 Login successful. Have fun.',
                         # TYPE I
                         '200 Binary it is, then.',
                         # PASV
                         '227 Entering Passive Mode (127,0,0,1,%d,%d)' %
                         (n>>8, n&0xff),
                         # RETR /file/that/doesnt/exist
                         '550 Failed to open file.']

            b = StringIOWithoutClosing()
            client = ftp.FTPClient(passive=1)
            client.makeConnection(protocol.FileWrapper(b))
            self.writeResponses(client, responses)
            p = protocol.Protocol()
            d = client.retrieveFile('/file/that/doesnt/exist', p)
            d.addCallback(lambda r, self=self:
                            self.fail('Callback incorrectly called: %r' % r))
            d.addBoth(lambda ignored,r=reactor: r.crash())

            id = reactor.callLater(2, self.timeout)
            reactor.run()
            log.flushErrors(ftp.FTPError)
            try:
                id.cancel()
            except:
                pass
        finally:
            try:
                port.stopListening()
                reactor.iterate()
            except:
                pass
    
    def timeout(self):
        reactor.crash()
        self.fail('Timed out')

    def writeResponses(self, protocol, responses):
        for response in responses:
            reactor.callLater(0.1, protocol.lineReceived, response)

    def testErrbacksUponDisconnect(self):
        ftpClient = ftp.FTPClient()
        d = ftpClient.list('some path', Dummy())
        m = []
        def _eb(failure):
            m.append(failure)
            return None
        d.addErrback(_eb)
        from twisted.internet.main import CONNECTION_LOST
        ftpClient.connectionLost(failure.Failure(CONNECTION_LOST))
        self.failUnless(1, len(m))

