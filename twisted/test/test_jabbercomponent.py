#
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

import sys, os, sha
from twisted.trial import unittest

from twisted.protocols.jabber.component import ComponentAuthenticator
from twisted.protocols import xmlstream

class ComponentAuthTest(unittest.TestCase):
    def authPassed(self, stream):
        self.authComplete = True
        
    def testAuth(self):
        self.authComplete = False
        outlist = []

        ca = ComponentAuthenticator("cjid", "secret")
        xs = xmlstream.XmlStream(ca)

        xs.addObserver(xmlstream.STREAM_AUTHD_EVENT,
                       self.authPassed)
        xs.send = outlist.append

        # Go...
        xs.connectionMade()
        xs.dataReceived("<stream:stream xmlns='jabber:component:accept' xmlns:stream='http://etherx.jabber.org/streams' from='cjid' id='12345'>")

        # Calculate what we expect the handshake value to be
        hv = sha.new("%s%s" % ("12345", "secret")).hexdigest()

        self.assertEquals(outlist[1].toXml(),
                          "<handshake>%s</handshake>" % (hv))

        xs.dataReceived("<handshake/>")

        self.assertEquals(self.authComplete, True)
        
            
