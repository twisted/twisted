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
from twisted.web import server, static, client, error, util
from twisted.internet import reactor

import os


class WebClientTestCase(unittest.TestCase):
    
    def setUp(self):
        name = str(id(self)) + "_webclient"
        if not os.path.exists(name):
            os.mkdir(name)
            f = open(os.path.join(name, "file"), "wb")
            f.write("0123456789")
            f.close()
        r = static.File(name)
        r.putChild("redirect", util.Redirect("/file"))
        self.port = reactor.listenTCP(0, server.Site(r), interface="127.0.0.1")
        reactor.iterate(); reactor.iterate()
        self.portno = self.port.getHost()[2]

    def tearDown(self):
        self.port.stopListening()
        reactor.iterate(); reactor.iterate()
        del self.port

    def getURL(self, path):
        return "http://127.0.0.1:%d/%s" % (self.portno, path)

    def testGetPage(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getURL("file"))),
                          "0123456789")

    def testDownloadPage(self):
        name = self.mktemp()
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name))
        self.assertEquals(open(name, "rb").read(), "0123456789")

    def testError(self):
        f = unittest.deferredError(client.getPage(self.getURL("nosuchfile")))
        f.trap(error.Error)

    def testRedirect(self):
        self.assertEquals(unittest.deferredResult(client.getPage(self.getURL("redirect"))),
                          "0123456789")

    def testPartial(self):
        name = self.mktemp()
        f = open(name, "wb")
        f.write("abcd")
        f.close()
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name,
                                                        supportPartial=1))
        self.assertEquals(open(name, "rb").read(), "abcd456789")
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name,
                                                        supportPartial=1))
        self.assertEquals(open(name, "rb").read(), "abcd456789")
        r = unittest.deferredResult(client.downloadPage(self.getURL("file"), name))
        self.assertEquals(open(name, "rb").read(), "0123456789")
