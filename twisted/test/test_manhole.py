
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
from twisted.manhole import service

class DummyManholeClient:
    zero = 0
    def __init__(self):
        self.messages = []

    def console(self, messages):
        self.messages.extend(messages)

    def receiveExplorer(self, xplorer):
        pass

    def setZero(self):
        self.zero = len(self.messages)

    def getMessages(self):
        return self.messages[self.zero:]

class DummyApp:
    name = 'None'
    def addService(self, serv):
        pass

class ManholeTest(unittest.TestCase):
    def setUp(self):
        self.service = service.Service(application=DummyApp())
        self.p = service.Perspective("UnitTest")
        self.p.setService(self.service)
        self.client = DummyManholeClient()
        self.p.attached(self.client, None)

    def test_importIdentity(self):
        """Making sure imported module is the same as one previously loaded.
        """
        self.p.perspective_do("from twisted.manhole import service")
        self.client.setZero()
        self.p.perspective_do("service is sys.modules['twisted.manhole.service']")
        msg = self.client.getMessages()[0]
        self.failUnlessEqual(msg, ('result',"1\n"))

    def test_importMain(self):
        """Trying to import __main__"""
        self.client.setZero()
        self.p.perspective_do("import __main__")
        if self.client.getMessages():
            msg = self.client.getMessages()[0]
            if msg[0] in ("exception","stderr"):
                self.fail(msg[1])

#if __name__=='__main__':
#    unittest.main()
