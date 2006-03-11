# -*- test-case-name: twisted.web.test.test_xmlrpc -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""Test XML-RPC support."""

import xmlrpclib
from twisted.web2 import xmlrpc
from twisted.web2 import server
from twisted.web2.channel import http
from twisted.web2.xmlrpc import XMLRPC, addIntrospection
from twisted.trial import unittest
from twisted.internet import reactor, defer
from twisted.python import log

try:
    from twisted.web.xmlrpc import Proxy
except ImportError:
    Proxy = None

import time

class TestRuntimeError(RuntimeError):
    pass

class TestValueError(ValueError):
    pass

class Test(XMLRPC):

    FAILURE = 666
    NOT_FOUND = 23
    SESSION_EXPIRED = 42

    addSlash = True # cause it's at the root
    
    # the doc string is part of the test
    def xmlrpc_add(self, request, a, b):
        """This function add two numbers."""
        return a + b

    xmlrpc_add.signature = [['int', 'int', 'int'],
                            ['double', 'double', 'double']]

    # the doc string is part of the test
    def xmlrpc_pair(self, request, string, num):
        """This function puts the two arguments in an array."""
        return [string, num]

    xmlrpc_pair.signature = [['array', 'string', 'int']]

    # the doc string is part of the test
    def xmlrpc_defer(self, request, x):
        """Help for defer."""
        return defer.succeed(x)

    def xmlrpc_deferFail(self, request):
        return defer.fail(TestValueError())

    # don't add a doc string, it's part of the test
    def xmlrpc_fail(self, request):
        raise TestRuntimeError

    def xmlrpc_fault(self, request):
        return xmlrpc.Fault(12, "hello")

    def xmlrpc_deferFault(self, request):
        return defer.fail(xmlrpc.Fault(17, "hi"))

    def xmlrpc_complex(self, request):
        return {"a": ["b", "c", 12, []], "D": "foo"}

    def xmlrpc_dict(self, request, map, key):
        return map[key]

    def getFunction(self, functionPath):
        try:
            return XMLRPC.getFunction(self, functionPath)
        except xmlrpc.NoSuchFunction:
            if functionPath.startswith("SESSION"):
                raise xmlrpc.Fault(self.SESSION_EXPIRED, "Session non-existant/expired.")
            else:
                raise

    xmlrpc_dict.help = 'Help for dict.'


class XMLRPCTestCase(unittest.TestCase):
    
    if not Proxy:
        skip = "Until web2 has an XML-RPC client, this test requires twisted.web."

    def setUp(self):
        self.p = reactor.listenTCP(0, http.HTTPFactory(server.Site(Test())),
                                   interface="127.0.0.1")
        self.port = self.p.getHost().port

    def tearDown(self):
        return self.p.stopListening()

    def proxy(self):
        return Proxy("http://127.0.0.1:%d/" % self.port)

    def testResults(self):
        inputOutput = [
            ("add", (2, 3), 5),
            ("defer", ("a",), "a"),
            ("dict", ({"a": 1}, "a"), 1),
            ("pair", ("a", 1), ["a", 1]),
            ("complex", (), {"a": ["b", "c", 12, []], "D": "foo"})]

        dl = []
        for meth, args, outp in inputOutput:
            d = self.proxy().callRemote(meth, *args)
            d.addCallback(self.assertEquals, outp)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

    def testErrors(self):
        dl = []
        for code, methodName in [(666, "fail"), (666, "deferFail"),
                                 (12, "fault"), (23, "noSuchMethod"),
                                 (17, "deferFault"), (42, "SESSION_TEST")]:
            d = self.proxy().callRemote(methodName)
            d = self.assertFailure(d, xmlrpc.Fault)
            d.addCallback(lambda exc, code=code: self.assertEquals(exc.faultCode, code))
            dl.append(d)
        d = defer.DeferredList(dl, fireOnOneErrback=True)
        d.addCallback(lambda ign: log.flushErrors(TestRuntimeError, TestValueError))
        return d


class XMLRPCTestCase2(XMLRPCTestCase):
    """Test with proxy that doesn't add a slash."""

    def proxy(self):
        return Proxy("http://127.0.0.1:%d" % self.port)


class XMLRPCTestIntrospection(XMLRPCTestCase):

    def setUp(self):
        xmlrpc = Test()
        addIntrospection(xmlrpc)
        self.p = reactor.listenTCP(0, http.HTTPFactory(server.Site(xmlrpc)),
            interface="127.0.0.1")
        self.port = self.p.getHost().port

    def testListMethods(self):

        def cbMethods(meths):
            meths.sort()
            self.failUnlessEqual(
                meths,
                ['add', 'complex', 'defer', 'deferFail',
                 'deferFault', 'dict', 'fail', 'fault',
                 'pair', 'system.listMethods',
                 'system.methodHelp',
                 'system.methodSignature'])

        d = self.proxy().callRemote("system.listMethods")
        d.addCallback(cbMethods)
        return d

    def testMethodHelp(self):
        inputOutputs = [
            ("defer", "Help for defer."),
            ("fail", ""),
            ("dict", "Help for dict.")]

        dl = []
        for meth, expected in inputOutputs:
            d = self.proxy().callRemote("system.methodHelp", meth)
            d.addCallback(self.assertEquals, expected)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

    def testMethodSignature(self):
        inputOutputs = [
            ("defer", ""),
            ("add", [['int', 'int', 'int'],
                     ['double', 'double', 'double']]),
            ("pair", [['array', 'string', 'int']])]

        dl = []
        for meth, expected in inputOutputs:
            d = self.proxy().callRemote("system.methodSignature", meth)
            d.addCallback(self.assertEquals, expected)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

