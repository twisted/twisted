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

import sys, types, os.path, re
from StringIO import StringIO

from twisted import internet
from twisted.trial import unittest
from twisted.protocols import basic
from twisted.internet import reactor, protocol, defer, interfaces
from twisted.cred import error, portal, checkers, credentials
from twisted.python import log, components, failure

from twisted.protocols import loopback


import ftp
from dav import ftpdav

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

class MyVirtualFTP(ftp.FTP):
    def connectionMade(self):
        ftp.FTP.connectionMade(self)

    def loadAvatar(self):
        self.shell = BogusAvatar()


class SimpleProtocol(object, basic.LineReceiver):
    connLost = None
    maxNumLines = None

    def __init__(self):
        self.conn = defer.Deferred()
        self.lineRx = defer.Deferred()
        self.lines = []
    
    numLines = property(lambda self: len(self.lines)) 

    def connectionMade(self):
        d, self.conn = self.conn, defer.Deferred()
        d.callback(None)

    def lineReceived(self, line):
        self.lines.append(line)
        if self.maxNumLines is not None and self.numLines >= self.maxNumLines:
            d, self.lineRx = self.lineRx, defer.Deferred()
            d.callback(None)
            
    def connectionLost(self, reason):
        self.connLost = 1
        self.lineRx.callback(None)
        self.conn.callback(None)


def createServerAndClient():
    factory = ftp.Factory()
    factory.maxProtocolInstances = None

    protocol = MyVirtualFTP()
    protocol.factory = factory

    # TODO Change this when we start testing the fs-related commands
    realm = ftpdav.Realm(os.getcwd())   
    p = portal.Portal(realm)
    p.registerChecker(checkers.AllowAnonymousAccess(), credentials.IAnonymous)
    protocol.portal = p
    client = SimpleProtocol()
    client.factory = internet.protocol.Factory()
    return (protocol, client)


def _eb(self, failure):
    log.err(failure)

def makeFuncObj(f, func_name):
    import types
    f = types.FunctionType(f.func_code, f.func_globals, func_name, f.func_defaults, f.func_closure)
    return f


class GreetingProto(SimpleProtocol):
    def lineReceived(self, line):
        SimpleProtocol.lineReceived(self, line)
        if len(self.lines) >= 2:
            self.transport.loseConnection()

def _eb(self, r):
    log.err(r)

class SimpleTests(unittest.TestCase):
    loopbackFunc = loopback.loopback
    user = 'studebaker_hawk'

    def setUp(self):
        self.s, self.c = createServerAndClient()
    
    def tearDown(self):
        del self.s
        del self.c

    def test_Loopback(self):
        self.s, self.c = createServerAndClient()
        self.c.maxNumLines = 2
        self.c.lineRx.addCallback(lambda _: self.c.transport.loseConnection()).addErrback(_eb)
        loopback.loopback(self.s, self.c)
        self.failUnless(len(self.c.lines) == 2)
        
    def run_reply_test(self, sendALine, numLines):
        self.c.conn.addCallback(sendALine
                ).addErrback(_eb)

        self.c.lineRx.addCallback(lambda _:self.c.transport.loseConnection())
        self.c.maxNumLines = numLines
        self.loopbackFunc.im_func(self.s, self.c)

    def test_Greeting(self):
        self.s, self.c= createServerAndClient()
        self.c.maxNumLines = 2
        self.c.lineRx.addCallback(lambda _: self.c.transport.loseConnection()).addErrback(_eb)
        loopback.loopback(self.s, self.c)
        self.failUnlessEqual(self.c.lines, ftp.RESPONSE[ftp.WELCOME_MSG].split('\r\n'))


    def test_USER_no_params(self):
        def sendALine(result):
            self.c.sendLine('USER')
        self.run_reply_test(sendALine, 3)
        self.failUnlessEqual(self.c.lines[-1], ftp.RESPONSE[ftp.SYNTAX_ERR] % 'USER with no parameters')

    def test_USER_anon_login(self):
        def sendALine(result):
            self.c.sendLine('USER anonymous')
        self.run_reply_test(sendALine, 3)
        
        self.failUnlessEqual(self.c.lines[-1], ftp.RESPONSE[ftp.GUEST_NAME_OK_NEED_EMAIL])

    def test_USER_user_login(self):
        def sendALine(result):
            self.c.sendLine('USER %s' % self.user)
        self.run_reply_test(sendALine, 3)

        self.failUnlessEqual(self.c.lines[-1], ftp.RESPONSE[ftp.USR_NAME_OK_NEED_PASS] % self.user)

    def test_PASS_anon(self):
        self.s.user = ftp.Factory.userAnonymous
        
        def _(result):
            self.c.sendLine('PASS %s' % 'nooone@example.net')
        self.run_reply_test(_, 2)
        print self.c.lines[-1]

    test_PASS_anon.todo = 'not working'





# -- Client Tests -----------------------------------------------------------



#class FTPFileListingTests(unittest.TestCase):
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
#class FTPClientTests(unittest.TestCase):
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
#
#
#for n in [FTPFileListingTests, 
#          FTPClientTests]:
#    setattr(n, 'skip', 'skip client tests')



