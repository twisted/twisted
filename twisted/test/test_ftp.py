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

from pyunit import unittest
from twisted.protocols import ftp
from twisted.internet import reactor

FTP_PORT = 2121

class FTPTest(unittest.TestCase):
    def setUp(self):
        """Creates an FTP server
        
        The FTP will serve files from the directory this module resides in.
        """
        self.serverFactory = ftp.FTPFactory()
        import test_ftp         # Myself
        import os.path
        serverPath = os.path.dirname(test_ftp.__file__)
        self.serverFactory.root = serverPath

        self.serverPort = reactor.listenTCP(FTP_PORT, self.serverFactory)

    def tearDown(self):
        self.serverPort.loseConnection()
        # Make sure the port really is closed, to avoid "address already in use"
        # errors.
        reactor.iterate()


class FTPClientTests(FTPTest):
    """These test the FTP Client against the FTP Server"""
    passive = 0
    
    def testFileListings(self):
        client = ftp.FTPClient(passive=self.passive)
        reactor.clientTCP('localhost', FTP_PORT, client)
        fileListing = ftp.FTPFileListProtocol()
        d = client.list('.', fileListing)
        d.addCallbacks(self.gotListing, self.errback)
        d.arm()

        while not hasattr(self, 'listing'):
            reactor.iterate()
        
        del self.listing
        
    def gotListing(self, listing):
        self.listing = listing

        # Check that the listing contains this file (test_ftp.py)
        filenames = map(lambda file: file['filename'], listing.files)
        self.failUnless('test_ftp.py' not in filenames, 
                        'test_ftp.py not in file listing')

    def errback(self, failure):
        self.fail('Errback called: ' + str(failure))
        

class FTPPassiveClientTests(FTPClientTests):
    """Identical to FTPClientTests, except with passive transfers.
    
    That's right ladies and gentlemen!  I double the number of tests with a
    trivial subclass!  Hahaha!
    """
    passive = 1


class FTPFileListingTests(unittest.TestCase):
    def TestOneLine(self):
        # This example line taken from the docstring for FTPFileListProtocol
        fileList = ftp.FTPFileListProtocol()
        fileList.dataReceived('-rw-r--r--   1 root     other        531 Jan 29 03:26 README')
        file = fileList.files[0]
        self.failUnless(file['filetype'] == '-', 'misparsed fileitem')
        self.failUnless(file['perms'] == 'rw-r--r--', 'misparsed perms')
        self.failUnless(file['owner'] == 'root', 'misparsed fileitem')
        self.failUnless(file['group'] == 'other', 'misparsed fileitem')
        self.failUnless(file['size'] == 531, 'misparsed fileitem')
        self.failUnless(file['date'] == 'Jan 29 03:26', 'misparsed fileitem')
        self.failUnless(file['filename'] == 'README', 'misparsed fileitem')

