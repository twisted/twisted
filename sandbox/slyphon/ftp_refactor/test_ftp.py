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

Maintainer: slyphon (Jonathan D. Simms)
"""

from __future__ import  nested_scopes

import os, sys, types, re
import os.path as osp
from StringIO import StringIO

from twisted import internet
from twisted.trial import unittest
from twisted.protocols import basic, loopback, policies
from twisted.internet import reactor, protocol, defer, interfaces
from twisted.cred import error, portal, checkers, credentials
from twisted.python import log, components, failure


# XXX: this is only temporary!!
sys.path.append(osp.dirname(os.getcwd()))
from ftp_refactor import ftp, ftpdav


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


class BogusAvatar(object):
    __implements__ = (ftp.IShell,)
    filesize = None
    bogusSize = 42
    bogusMdtm = 'YYMMDDHHMMSS'
    bogusPwd = '/alt/fun/your_ass'
    
    def __init__(self):
        self.user     = None        # user name
        self.uid      = None        # uid of anonymous user for shell
        self.gid      = None        # gid of anonymous user for shell
        self.clientwd = None
        self.tld      = None
        self.debug    = True 

    def pwd(self):
        return self.bogusPwd

    def cwd(self, path):
        pass

    def cdup(self):
        self.cdupCalled = True

    def dele(self, path):
        self.delePath = path

    def mkd(self, path):
        self.mkdPath = path

    def rmd(self, path):
        self.rmdPath = path

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
        self.mdtmPath = path
        return self.bogusMdtm

    def size(self, path):
        self.sizePath = path
        return self.bogusSize

    def nlist(self, path):
        pass


class MyVirtualFTP(ftp.FTP):
    def connectionMade(self):
        ftp.FTP.connectionMade(self)

    def loadAvatar(self):
        self.shell = BogusAvatar()


class SimpleProtocol(object, basic.LineReceiver, policies.TimeoutMixin):
    connLost = None
    maxNumLines = None

    def __init__(self, timeout=None):
        self.conn = defer.Deferred()
        self.lineRx = defer.Deferred()
        self.connLost = defer.Deferred()
        self.rawData = []
        self.lines = []
        self.setTimeout(timeout)
    
    numLines = property(lambda self: len(self.lines)) 
    lastline = property(lambda self: self.lines[-1])

    def connectionMade(self):
        print 'SimpleProtocol.connectionMade!'
        self.resetTimeout()
        d, self.conn = self.conn, defer.Deferred()
        d.callback(None)

    def lineReceived(self, line):
        self.resetTimeout()
        self.lines.append(line)
        if self.maxNumLines is not None and self.numLines >= self.maxNumLines:
            d, self.lineRx = self.lineRx, defer.Deferred()
            d.callback(None)
            
    def connectionLost(self, reason):
        self.connLost = 1
        self.setTimeout(None)
        d, self.connLost = self.connLost, defer.Deferred()
        d.callback(None)

    def loseConnection(self):
        self.setTimeout(None)
        if self.transport:
            self.transport.loseConnection()

    def timeoutConnection(self):
        print 'Connection Timed Out!!!'
        policies.TimeoutMixin.timeoutConnection(self)

    def rawDataReceived(self, data):
        self.rawData.append(data)


class TestRealm(ftpdav.Realm):
    def requestAvatar(self, avatarID, mind, *interfaces):
        a = BogusAvatar()
        a.tld = os.getcwd()
        return ftp.IShell, a, None


class VeryInsecureChecker:
    __implements__ = (checkers.ICredentialsChecker,)

    credentialInterfaces = [credentials.IUsernamePassword]
    
    def requestAvatarId(self, credentials):
        return credentials.username


class SlightlyLessInsecureChecker(VeryInsecureChecker):
    def requestAvatarId(self, credentials):
        if (credentials.username == 'studebaker_hawk' and
            credentials.password == 'ethel_a_tree'):
            return credentials.username
        else:
            raise error.UnauthorizedLogin()


def resp(code, arg=None):
    return ftp.RESPONSE[code]

def _eb(r):
    log.err(r)

class SimpleTestBase(unittest.TestCase):
    loopbackFunc = loopback.loopback
    def setUp(self):
        self.testpath = '/a/file/path/to/delete'
        self.loadTestRealm = False
        self.upChecker = VeryInsecureChecker()
        self.s, self.c = self.createServerAndClient(timeout=2)
    
    def tearDown(self):
        [n.cancel() for n in reactor.getDelayedCalls()]
        del self.s
        del self.c

    def createServerAndClient(self, timeout=None):
        factory = ftp.Factory()
        factory.maxProtocolInstances = None

        protocol = MyVirtualFTP()
        protocol.factory = factory

        # TODO Change this when we start testing the fs-related commands
        if not self.loadTestRealm:
            realm = ftpdav.Realm(os.getcwd())   
        else:
            realm = TestRealm()
        p = portal.Portal(realm)
        p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
        p.registerChecker(self.upChecker, credentials.IUsernamePassword)
        protocol.portal = p
        client = SimpleProtocol(timeout)
        client.factory = internet.protocol.Factory()
        return (protocol, client)


#class SimpleTests(SimpleTestBase):
#    user = 'studebaker_hawk'
#
#    def test_Loopback(self):
#        self.s, self.c = self.createServerAndClient()
#        self.c.maxNumLines = 2
#        self.c.lineRx.addCallback(lambda _: self.c.loseConnection()).addErrback(_eb)
#        #def _(r=None):
#        #    import pdb;pdb.set_trace() 
#        #self.c.lineRx.addCallback(_)
#        loopback.loopback(self.s, self.c)
#        self.failUnless(len(self.c.lines) == 2)
#
#    def runRespTest(self, cmd, resp):
#        self.run_reply_test(lambda _:self.c.sendLine(cmd), 3)
#        self.failUnlessEqual(self.c.lastline, resp)
#        
#    def run_reply_test(self, sendALine, numLines):
#        self.c.conn.addCallback(sendALine
#                ).addErrback(_eb)
#
#        self.c.lineRx.addCallback(lambda _:self.c.loseConnection()).addErrback(_eb)
#        self.c.maxNumLines = numLines
#        self.loopbackFunc.im_func(self.s, self.c)
#
#    print "\n\nWARNING: psyco optimizations running\n\n"
#    import psyco
#    psyco.bind(runRespTest)
#    psyco.bind(run_reply_test)
#        
#    def test_Greeting(self):
#        self.s, self.c = self.createServerAndClient()
#        self.c.maxNumLines = 2
#        self.c.lineRx.addCallback(lambda _: self.c.loseConnection()).addErrback(_eb)
#        loopback.loopback(self.s, self.c)
#        self.failUnlessEqual(self.c.lines, resp(ftp.WELCOME_MSG).split('\r\n'))
#
#    def test_USER_no_params(self):
#        self.runRespTest('USER', resp(ftp.SYNTAX_ERR) % 'USER with no parameters')
#
#    def test_USER_anon_login(self):
#        self.runRespTest('USER anonymous', resp(ftp.GUEST_NAME_OK_NEED_EMAIL))
#
#    def test_USER_user_login(self):
#        self.runRespTest('USER %s' % self.user, resp(ftp.USR_NAME_OK_NEED_PASS) % self.user) 
#
#    def test_PASS_anon(self):
#        self.s.user = ftp.Factory.userAnonymous
#        self.runRespTest('PASS %s' % 'nooone@example.net', resp(ftp.GUEST_LOGGED_IN_PROCEED))
#       
#    def test_PASS_user(self):
#        self.loadTestRealm = True
#        self.tearDown(); 
#        self.s, self.c = self.createServerAndClient(timeout=2)
#        self.failUnless(isinstance(self.s.portal.realm, TestRealm), 'self.s.portal.realm is not TestRealm!')
#        self.s.user = self.user
#
#        self.runRespTest('PASS %s' % 'apassword', resp(ftp.USR_LOGGED_IN_PROCEED))
#
#    def test_PASS_user_fail(self):
#        self.loadTestRealm = True
#        self.upChecker = SlightlyLessInsecureChecker()
#        self.tearDown() 
#        self.s, self.c = self.createServerAndClient(timeout=2)
#        self.failUnless(isinstance(self.s.portal.realm, TestRealm), 'self.s.portal.realm is not TestRealm!')
#        self.s.user = self.user
#
#        self.runRespTest('PASS %s' % 'apassword', resp(ftp.AUTH_FAILURE) % '')
#
#    def test_TYPE(self):
#        okParams = ['I', 'A', 'L', 'i', 'a', 'l']
#        for arg in okParams:
#            self.s.shell = True
#            self.runRespTest('TYPE %s' % arg, resp(ftp.TYPE_SET_OK) % arg.upper())
#            self.tearDown(); self.setUp()
#
#        for arg in [chr(x) for x in xrange(97,123)]:
#            if arg not in okParams:
#                self.s.shell = True
#                self.runRespTest('TYPE %s' % arg, resp(ftp.SYNTAX_ERR_IN_ARGS) % arg.upper())
#                self.tearDown(); self.setUp()
#            else:
#                continue
#
#    def test_SYST(self):
#        self.s.shell = True
#        self.runRespTest('SYST', resp(ftp.NAME_SYS_TYPE))
#
#    def test_SIZE(self):
#        self.s.loadAvatar()
#        self.runRespTest('SIZE %s' % self.testpath, resp(ftp.FILE_STATUS) % self.s.shell.bogusSize)
#        self.failUnlessEqual(self.testpath, self.s.shell.sizePath)
#
#    def test_MDTM(self):
#        self.s.loadAvatar()
#        self.runRespTest('MDTM %s' % self.testpath, resp(ftp.FILE_STATUS) % self.s.shell.bogusMdtm)
#        self.failUnlessEqual(self.testpath, self.s.shell.mdtmPath)
#
#    def test_PWD(self):
#        self.s.loadAvatar()
#        self.runRespTest('PWD', resp(ftp.PWD_REPLY) % self.s.shell.bogusPwd)
#
#    def test_PASV(self):
#        self.s.loadAvatar()
#        self.run_reply_test(lambda _:self.c.sendLine('PASV'), 3)
#        self.assert_(re.search(r'227 =.*,[0-2]?[0-9]?[0-9],[0-2]?[0-9]?[0-9]',self.c.lastline))
#        
#    def test_PORT(self):
#        self.s.loadAvatar()
#        self.runRespTest('PORT' , resp(ftp.CMD_NOT_IMPLMNTD) % 'PORT')
#
#    def test_CDUP(self):
#        self.s.loadAvatar()
#        self.runRespTest('CDUP', resp(ftp.REQ_FILE_ACTN_COMPLETED_OK))
#        self.failUnless(hasattr(self.s.shell, 'cdupCalled'))
#
#    def test_STRU(self):
#        self.s.loadAvatar()
#        self.runRespTest('STRU F', resp(ftp.CMD_OK))
#
#        self.tearDown(); self.setUp()
#        
#        self.s.loadAvatar()
#        arg = 'Q'
#        self.runRespTest('STRU %s' % arg, resp(ftp.CMD_NOT_IMPLMNTD_FOR_ARG) % arg)
#
#    def test_MODE(self):
#        self.s.loadAvatar()
#        self.runRespTest('MODE S', resp(ftp.CMD_OK))
#
#        self.tearDown(); self.setUp()
#        
#        self.s.loadAvatar()
#        arg = 'Q'
#        self.runRespTest('MODE %s' % arg, resp(ftp.CMD_NOT_IMPLMNTD_FOR_ARG) % arg)
#
#    def test_DELE(self):
#        self.s.loadAvatar()
#        self.runRespTest('DELE %s' % self.testpath, resp(ftp.REQ_FILE_ACTN_COMPLETED_OK))
#        self.failUnless(self.s.shell.delePath == self.testpath)
#
#    def test_MKD(self):
#        self.s.loadAvatar()
#        self.runRespTest('MKD %s' % self.testpath, resp(ftp.REQ_FILE_ACTN_COMPLETED_OK))
#        self.failUnless(self.s.shell.mkdPath == self.testpath)
#
#    def test_RMD(self):
#        self.s.loadAvatar()
#        self.runRespTest('RMD %s' % self.testpath, resp(ftp.REQ_FILE_ACTN_COMPLETED_OK))
#        self.failUnless(self.s.shell.rmdPath == self.testpath)
#
#    def test_STOU(self):
#        cmd = 'STOU'
#        self.s.loadAvatar()
#        self.runRespTest(cmd, resp(ftp.CMD_NOT_IMPLMNTD) % cmd)
#
#    def test_QUIT(self):
#        self.s.loadAvatar()
#        self.run_reply_test(lambda _:self.c.sendLine('QUIT'), 3)
#        self.failUnless(self.c.connLost)


class DtpRelatedTests(unittest.TestCase):
    loopbackFunc = loopback.loopback
    def setUp(self):
        self.testpath = '/a/file/path/to/delete'
        self.loadTestRealm = False
        self.upChecker = VeryInsecureChecker()
        self.s, self.c = self.createServerAndClient(timeout=2)
        self.hookUpDtp()
    
    def tearDown(self):
        [n.cancel() for n in reactor.getDelayedCalls()]
        del self.s
        del self.c

    def createServerAndClient(self, timeout=None):
        factory = ftp.Factory()
        factory.maxProtocolInstances = None

        protocol = MyVirtualFTP()
        protocol.factory = factory

        # TODO Change this when we start testing the fs-related commands
        if not self.loadTestRealm:
            realm = ftpdav.Realm(os.getcwd())   
        else:
            realm = TestRealm()
        p = portal.Portal(realm)
        p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
        p.registerChecker(self.upChecker, credentials.IUsernamePassword)
        protocol.portal = p
        client = SimpleProtocol(timeout)
        client.factory = internet.protocol.Factory()
        return (protocol, client)

       
    def hookUpDtp(self):
        self.s.dtpTxfrMode = ftp.PASV

        ds = ftp.DTP()
        ds.pi = self.s
        ds.pi.dtpInstance = ds
        ds.pi.dtpPort = ('i','',0)

        ds.factory = ftp.DTPFactory(self.s)
        self.s.dtpFactory = ds.factory
        self.ds = ds

        self.s._FTP__TestingSoJustSkipTheReactorStep = True

        dc = SimpleProtocol()
        dc.factory = protocol.ClientFactory()
        dc.factory.protocol = SimpleProtocol
        dc.setRawMode()
        self.dc = dc
    
    def test_LIST(self):
        self.s.loadAvatar()
        ds = self.ds
        dc = self.dc

        def lo(result):
            print "setting up loopback"
            loopback.loopback(ds, dc)
        self.c.conn.addCallback(lo
                ).addCallback(lambda _:self.c.sendLine('LIST /')
                ).addErrback(_eb)
        self.dc.conn.addCallback(lambda _: log.msg('connected dtp protocol')
                ).addErrback(_eb)
        self.dc.connLost.addCallback(lambda _:self.c.loseConnection()).addErrback(_eb)
        self.loopbackFunc(self.s, self.c)





# -- Client Tests -----------------------------------------------------------
#class NonClosingStringIO(StringIO):
#    def close(self):
#        pass
#
#StringIOWithoutClosing = NonClosingStringIO
#
#
#class FileListingTests(unittest.TestCase):
#    def testOneLine(self):
#        # This example line taken from the docstring for FTPFileListProtocol
#        fileList = ftp.FTPFileListProtocol()
#        class PrintLine(protocol.Protocol):
#            def connectionMade(self):
#                self.transport.write('-rw-r--r--   1 root     other        531 Jan 29 03:26 README\n')
#                self.transport.loseConnection()
#        loopback.loopback(PrintLine(), fileList)
#        file = fileList.files[0]
#        self.failUnless(file['filetype'] == '-', 'misparsed fileitem')
#        self.failUnless(file['perms'] == 'rw-r--r--', 'misparsed perms')
#        self.failUnless(file['owner'] == 'root', 'misparsed fileitem')
#        self.failUnless(file['group'] == 'other', 'misparsed fileitem')
#        self.failUnless(file['size'] == 531, 'misparsed fileitem')
#        self.failUnless(file['date'] == 'Jan 29 03:26', 'misparsed fileitem')
#        self.failUnless(file['filename'] == 'README', 'misparsed fileitem')
#
#class ClientTests(unittest.TestCase):
#    def testFailedRETR(self):
#        try:
#            f = protocol.Factory()
#            f.noisy = 0
#            f.protocol = protocol.Protocol
#            port = reactor.listenTCP(0, f, interface="127.0.0.1")
#            n = port.getHost()[2]
#            # This test data derived from a bug report by ranty on #twisted
#            responses = ['220 ready, dude (vsFTPd 1.0.0: beat me, break me)',
#                         # USER anonymous
#                         '331 Please specify the password.',
#                         # PASS twisted@twistedmatrix.com
#                         '230 Login successful. Have fun.',
#                         # TYPE I
#                         '200 Binary it is, then.',
#                         # PASV
#                         '227 Entering Passive Mode (127,0,0,1,%d,%d)' %
#                         (n>>8, n&0xff),
#                         # RETR /file/that/doesnt/exist
#                         '550 Failed to open file.']
#
#            b = StringIOWithoutClosing()
#            client = ftp.FTPClient(passive=1)
#            client.makeConnection(protocol.FileWrapper(b))
#            self.writeResponses(client, responses)
#            p = protocol.Protocol()
#            d = client.retrieveFile('/file/that/doesnt/exist', p)
#            d.addCallback(lambda r, self=self:
#                            self.fail('Callback incorrectly called: %r' % r))
#            d.addBoth(lambda ignored,r=reactor: r.crash())
#
#            id = reactor.callLater(2, self.timeout)
#            reactor.run()
#            log.flushErrors(ftp.FTPError)
#            try:
#                id.cancel()
#            except:
#                pass
#        finally:
#            try:
#                port.stopListening()
#                reactor.iterate()
#            except:
#                pass
#
#    def timeout(self):
#        reactor.crash()
#        self.fail('Timed out')
#
#    def writeResponses(self, protocol, responses):
#        for response in responses:
#            reactor.callLater(0.1, protocol.lineReceived, response)
#



