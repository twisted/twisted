# -*- test-case-name: twisted.web.test.test_xmlrpc -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""Test XML-RPC support."""

import xmlrpclib

from twisted.web2 import xmlrpc
from twisted.web2.xmlrpc import XMLRPC, addIntrospection
from twisted.internet import defer

from twisted.web2.test.test_server import BaseCase

class TestRuntimeError(RuntimeError):
    """
    Fake RuntimeError for testing purposes.
    """

class TestValueError(ValueError):
    """
    Fake ValueError for testing purposes.
    """

class XMLRPCTestResource(XMLRPC):
    """
    This is the XML-RPC "server" against which the tests will be run.
    """
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

class XMLRPCServerBase(BaseCase):
    """
    The parent class of the XML-RPC test classes.
    """
    method = 'POST'
    version = (1, 1)

    def setUp(self):
        self.root = XMLRPCTestResource()
        self.xml = ("<?xml version='1.0'?>\n<methodResponse>\n" +
            "%s</methodResponse>\n")

class XMLRPCServerGETTest(XMLRPCServerBase):
    """
    Attempt access to the RPC resources as regular HTTP resource.
    """

    def setUp(self):
        super(XMLRPCServerGETTest, self).setUp()
        self.method = 'GET'
        self.errorRPC = ('<html><head><title>XML-RPC responder</title>' +
            '</head><body><h1>XML-RPC responder</h1>POST your XML-RPC ' +
            'here.</body></html>')
        self.errorHTTP = ('<html><head><title>404 Not Found</title>' +
            '</head><body><h1>Not Found</h1>The resource http://host/add ' +
            'cannot be found.</body></html>')

    def test_rootGET(self):
        """
        Test a simple GET against the XML-RPC server.
        """
        return self.assertResponse(
            (self.root, 'http://host/'),
            (200, {}, self.errorRPC))

    def test_childGET(self):
        """
        Try to access an XML-RPC method as a regular resource via GET.
        """
        return self.assertResponse(
            (self.root, 'http://host/add'),
            (404, {}, self.errorHTTP))

class XMLRPCServerPOSTTest(XMLRPCServerBase):
    """
    Tests for standard XML-RPC usage.
    """
    def test_RPCMethods(self):
        """
        Make RPC calls of the defined methods, checking for the expected 
        results.
        """
        inputOutput = [
            ("add", (2, 3), 5),
            ("defer", ("a",), "a"),
            ("dict", ({"a": 1}, "a"), 1),
            ("pair", ("a", 1), ["a", 1]),
            ("complex", (), {"a": ["b", "c", 12, []], "D": "foo"})]
        dl = []
        for meth, args, outp in inputOutput:
            postdata = xmlrpclib.dumps(args, meth)
            respdata = xmlrpclib.dumps((outp,))
            reqdata = (self.root, 'http://host/', {}, None, None, '', postdata)
            d = self.assertResponse(reqdata, (200, {}, self.xml % respdata))
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

    def test_RPCFaults(self):
        """
        Ensure that RPC faults are properly processed.
        """
        dl = []
        codeMethod = [
            (12, "fault", 'hello'),
            (23, "noSuchMethod", 'function noSuchMethod not found'),
            (17, "deferFault", 'hi'),
            (42, "SESSION_TEST", 'Session non-existant/expired.')]
        for code, meth, fault in codeMethod:
            postdata = xmlrpclib.dumps((), meth)
            respdata = xmlrpclib.dumps(xmlrpc.Fault(code, fault))
            reqdata = (self.root, 'http://host/', {}, None, None, '', postdata)
            d = self.assertResponse(reqdata, (200, {}, respdata))
            dl.append(d)
        d = defer.DeferredList(dl, fireOnOneErrback=True)
        return d

    def test_RPCFailures(self):
        """
        Ensure that failures behave as expected.
        """
        dl = []
        codeMethod = [
            (666, "fail"),
            (666, "deferFail")]
        for code, meth in codeMethod:
            postdata = xmlrpclib.dumps((), meth)
            respdata = xmlrpclib.dumps(xmlrpc.Fault(code, 'error'))
            reqdata = (self.root, 'http://host/', {}, None, None, '', postdata)
            d = self.assertResponse(reqdata, (200, {}, respdata))
            d.addCallback(self.flushLoggedErrors, TestRuntimeError, TestValueError)
            dl.append(d)
        d = defer.DeferredList(dl, fireOnOneErrback=True)
        return d

class XMLRPCTestIntrospection(XMLRPCServerBase):

    def setUp(self):
        """
        Introspection requires additional setup, most importantly, adding
        introspection to the root object.
        """
        super(XMLRPCTestIntrospection, self).setUp()
        addIntrospection(self.root)
        self.methodList = ['add', 'complex', 'defer', 'deferFail',
            'deferFault', 'dict', 'fail', 'fault', 'pair',
            'system.listMethods', 'system.methodHelp', 'system.methodSignature']

    def test_listMethods(self):
        """
        Check that the introspection method "listMethods" returns all the
        methods we defined in the XML-RPC server.
        """
        def cbMethods(meths):
            meths.sort()
            self.failUnlessEqual(
                meths,
                )
        postdata = xmlrpclib.dumps((), 'system.listMethods')
        respdata = xmlrpclib.dumps((self.methodList,))
        reqdata = (self.root, 'http://host/', {}, None, None, '', postdata)
        return self.assertResponse(reqdata, (200, {}, self.xml % respdata))

    def test_methodHelp(self):
        """
        Check the RPC methods for docstrings or .help attributes.
        """
        inputOutput = [
            ("defer", "Help for defer."),
            ("fail", ""),
            ("dict", "Help for dict.")]

        dl = []
        for meth, outp in inputOutput:
            postdata = xmlrpclib.dumps((meth,), 'system.methodHelp')
            respdata = xmlrpclib.dumps((outp,))
            reqdata = (self.root, 'http://host/', {}, None, None, '', postdata)
            d = self.assertResponse(reqdata, (200, {}, self.xml % respdata))
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

    def test_methodSignature(self):
        """
        Check that the RPC methods whose signatures have been set via the
        .signature attribute (on the method) are returned as expected.
        """
        inputOutput = [
            ("defer", ""),
            ("add", [['int', 'int', 'int'],
                     ['double', 'double', 'double']]),
            ("pair", [['array', 'string', 'int']])]

        dl = []
        for meth, outp in inputOutput:
            postdata = xmlrpclib.dumps((meth,), 'system.methodSignature')
            respdata = xmlrpclib.dumps((outp,))
            reqdata = (self.root, 'http://host/', {}, None, None, '', postdata)
            d = self.assertResponse(reqdata, (200, {}, self.xml % respdata))
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)


