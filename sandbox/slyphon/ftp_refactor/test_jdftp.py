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
from __future__ import  nested_scopes

from twisted.trial import unittest
from twisted.protocols import loopback
from twisted.internet import reactor, protocol
import jdftp as ftp

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import sys, types, os.path

from twisted.test.test_protocols import StringIOWithoutClosing

from twisted.python import log


class TelnetClientFactory(protocol.ClientFactory):
    protocol = protocol.Telnet
    instance = None

    def buildProtocol(self, addr):
        if self.instance:
            return
        p = protocol.ClientFactory.buildProtocol(self,addr)
        p.factory = self
        self.instance = p
        return p

class JDFtpTests(unittest.TestCase):
    def setUp(self):
        self.f = ftp.FTPFactory()
        self.t = TelnetClientFactory()
        


if __name__ == '__main__':

