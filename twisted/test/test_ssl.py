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

from twisted.trial import unittest
from twisted.internet import protocol, reactor
from twisted.internet import ssl
import os
import test_tcp


class ProperlyCloseFilesTestCase(test_tcp.ProperlyCloseFilesTestCase):
    
    def setUp(self):
        certPath = os.path.join(os.path.split(test_tcp.__file__)[0], "server.pem")
        f = protocol.ServerFactory()
        f.protocol = protocol.Protocol
        self.listener = reactor.listenSSL(
            0, f, ssl.DefaultOpenSSLContextFactory(certPath, certPath)
        )
        
        f = protocol.ClientFactory()
        f.protocol = test_tcp.ConnectionLosingProtocol
        f.protocol.master = self
        self.connector = (lambda p=self.listener.getHost()[2]:
            reactor.connectSSL('localhost', p, f, ssl.ClientContextFactory()))
        
        self.totalConnections = 0

    def testProperlyCloseFiles(self):
        raise unittest.SkipTest, "OpenSSL does not work"
