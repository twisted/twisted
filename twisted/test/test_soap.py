#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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

"""Test SOAP support."""

try:
    import SOAPpy
except ImportError:
    SOAPpy = None
    class SOAPPublisher: pass
else:
    from twisted.web import soap
    SOAPPublisher = soap.SOAPPublisher

from twisted.trial import unittest
from twisted.web import server
from twisted.internet import reactor, defer
from twisted.python import log


class Test(SOAPPublisher):

    def soap_add(self, a, b):
        return a + b

    def soap_kwargs(self, a=1, b=2):
        return a + b
    soap_kwargs.useKeywords=True
    
    def soap_pair(self, string, num):
        return [string, num, None]

    def soap_struct(self):
        return SOAPpy.structType({"a": "c"})
    
    def soap_defer(self, x):
        return defer.succeed(x)

    def soap_deferFail(self):
        return defer.fail(ValueError())

    def soap_fail(self):
        raise RuntimeError

    def soap_deferFault(self):
        return defer.fail(ValueError())

    def soap_complex(self):
        return {"a": ["b", "c", 12, []], "D": "foo"}

    def soap_dict(self, map, key):
        return map[key]


class SOAPTestCase(unittest.TestCase):

    def setUp(self):
        self.p = reactor.listenTCP(0, server.Site(Test()),
                                   interface="127.0.0.1")
        self.port = self.p.getHost()[2]

    def tearDown(self):
        self.p.stopListening()
        reactor.iterate()
        reactor.iterate()

    def proxy(self):
        return soap.Proxy("http://localhost:%d/" % self.port)

    def testResults(self):
        x = self.proxy().callRemote("add", 2, 3)
        self.assertEquals(unittest.deferredResult(x), 5)
        x = self.proxy().callRemote("kwargs", b=2, a=3)
        self.assertEquals(unittest.deferredResult(x), 5)
        x = self.proxy().callRemote("kwargs", b=3)
        self.assertEquals(unittest.deferredResult(x), 4)
        x = self.proxy().callRemote("defer", "a")
        self.assertEquals(unittest.deferredResult(x), "a")
        x = self.proxy().callRemote("dict", {"a" : 1}, "a")
        self.assertEquals(unittest.deferredResult(x), 1)
        x = self.proxy().callRemote("pair", 'a', 1)
        self.assertEquals(unittest.deferredResult(x), ['a', 1, None])
        x = self.proxy().callRemote("struct")
        self.assertEquals(unittest.deferredResult(x)._asdict,
                          {"a": "c"})
        x = self.proxy().callRemote("complex")
        self.assertEquals(unittest.deferredResult(x)._asdict,
                          {"a": ["b", "c", 12, []], "D": "foo"})

    def testErrors(self):
        pass
    testErrors.skip = "Not yet implemented"


if not SOAPpy:
    SOAPTestCase.skip = "SOAPpy not installed"
