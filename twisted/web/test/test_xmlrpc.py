# -*- test-case-name: twisted.web.test.test_xmlrpc -*-
#
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test XML-RPC support.
"""

try:
    import xmlrpclib
except ImportError:
    xmlrpclib = None
    class XMLRPC: pass
else:
    from twisted.web import xmlrpc
    from twisted.web.xmlrpc import XMLRPC, addIntrospection

from twisted.trial import unittest
from twisted.web import server, static, client, error, http
from twisted.internet import reactor, defer


class TestRuntimeError(RuntimeError):
    pass

class TestValueError(ValueError):
    pass



class Test(XMLRPC):

    FAILURE = 666
    NOT_FOUND = 23
    SESSION_EXPIRED = 42

    # the doc string is part of the test
    def xmlrpc_add(self, a, b):
        """
        This function add two numbers.
        """
        return a + b

    xmlrpc_add.signature = [['int', 'int', 'int'],
                            ['double', 'double', 'double']]

    # the doc string is part of the test
    def xmlrpc_pair(self, string, num):
        """
        This function puts the two arguments in an array.
        """
        return [string, num]

    xmlrpc_pair.signature = [['array', 'string', 'int']]

    # the doc string is part of the test
    def xmlrpc_defer(self, x):
        """Help for defer."""
        return defer.succeed(x)

    def xmlrpc_deferFail(self):
        return defer.fail(TestValueError())

    # don't add a doc string, it's part of the test
    def xmlrpc_fail(self):
        raise TestRuntimeError

    def xmlrpc_fault(self):
        return xmlrpc.Fault(12, "hello")

    def xmlrpc_deferFault(self):
        return defer.fail(xmlrpc.Fault(17, "hi"))

    def xmlrpc_complex(self):
        return {"a": ["b", "c", 12, []], "D": "foo"}

    def xmlrpc_dict(self, map, key):
        return map[key]

    def _getFunction(self, functionPath):
        try:
            return XMLRPC._getFunction(self, functionPath)
        except xmlrpc.NoSuchFunction:
            if functionPath.startswith("SESSION"):
                raise xmlrpc.Fault(self.SESSION_EXPIRED,
                                   "Session non-existant/expired.")
            else:
                raise

    xmlrpc_dict.help = 'Help for dict.'

class TestAuthHeader(Test):
    """
    This is used to get the header info so that we can test
    authentication.
    """
    def __init__(self):
        Test.__init__(self)
        self.request = None

    def render(self, request):
        self.request = request
        return Test.render(self, request)

    def xmlrpc_authinfo(self):
        return self.request.getUser(), self.request.getPassword()


class TestQueryProtocol(xmlrpc.QueryProtocol):
    """
    QueryProtocol for tests that saves headers received inside the factory.
    """
    def handleHeader(self, key, val):
        self.factory.headers[key.lower()] = val


class TestQueryFactory(xmlrpc._QueryFactory):
    """
    QueryFactory using L{TestQueryProtocol} for saving headers.
    """
    protocol = TestQueryProtocol

    def __init__(self, *args, **kwargs):
        self.headers = {}
        xmlrpc._QueryFactory.__init__(self, *args, **kwargs)


class XMLRPCTestCase(unittest.TestCase):

    def setUp(self):
        self.p = reactor.listenTCP(0, server.Site(Test()),
                                   interface="127.0.0.1")
        self.port = self.p.getHost().port
        self.factories = []

    def tearDown(self):
        self.factories = []
        return self.p.stopListening()

    def queryFactory(self, *args, **kwargs):
        """
        Specific queryFactory for proxy that uses our custom
        L{TestQueryFactory}, and save factories.
        """
        factory = TestQueryFactory(*args, **kwargs)
        self.factories.append(factory)
        return factory

    def proxy(self):
        p = xmlrpc.Proxy("http://127.0.0.1:%d/" % self.port)
        p.queryFactory = self.queryFactory
        return p

    def test_results(self):
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

    def test_errors(self):
        """
        Verify that for each way a method exposed via XML-RPC can fail, the
        correct 'Content-type' header is set in the response and that the
        client-side Deferred is errbacked with an appropriate C{Fault}
        instance.
        """
        dl = []
        for code, methodName in [(666, "fail"), (666, "deferFail"),
                                 (12, "fault"), (23, "noSuchMethod"),
                                 (17, "deferFault"), (42, "SESSION_TEST")]:
            d = self.proxy().callRemote(methodName)
            d = self.assertFailure(d, xmlrpc.Fault)
            d.addCallback(lambda exc, code=code:
                self.assertEquals(exc.faultCode, code))
            dl.append(d)
        d = defer.DeferredList(dl, fireOnOneErrback=True)
        def cb(ign):
            for factory in self.factories:
                self.assertEquals(factory.headers['content-type'],
                                  'text/xml')
            self.flushLoggedErrors(TestRuntimeError, TestValueError)
        d.addCallback(cb)
        return d

    def test_errorGet(self):
        """
        A classic GET on the xml server should return a NOT_ALLOWED.
        """
        d = client.getPage("http://127.0.0.1:%d/" % (self.port,))
        d = self.assertFailure(d, error.Error)
        d.addCallback(
            lambda exc: self.assertEquals(int(exc.args[0]), http.NOT_ALLOWED))
        return d

    def test_errorXMLContent(self):
        """
        Test that an invalid XML input returns an L{xmlrpc.Fault}.
        """
        d = client.getPage("http://127.0.0.1:%d/" % (self.port,),
                           method="POST", postdata="foo")
        def cb(result):
            self.assertRaises(xmlrpc.Fault, xmlrpclib.loads, result)
        d.addCallback(cb)
        return d


class XMLRPCTestCase2(XMLRPCTestCase):
    """
    Test with proxy that doesn't add a slash.
    """

    def proxy(self):
        p = xmlrpc.Proxy("http://127.0.0.1:%d" % self.port)
        p.queryFactory = self.queryFactory
        return p



class XMLRPCAllowNoneTestCase(unittest.TestCase):
    """
    Test with allowNone set to True.

    These are not meant to be exhaustive serialization tests, since
    L{xmlrpclib} does all of the actual serialization work.  They are just
    meant to exercise a few codepaths to make sure we are calling into
    xmlrpclib correctly.
    """

    def setUp(self):
        self.p = reactor.listenTCP(
            0, server.Site(Test(allowNone=True)), interface="127.0.0.1")
        self.port = self.p.getHost().port


    def tearDown(self):
        return self.p.stopListening()


    def proxy(self):
        return xmlrpc.Proxy("http://127.0.0.1:%d" % (self.port,),
                            allowNone=True)


    def test_deferredNone(self):
        """
        Test that passing a C{None} as an argument to a remote method and
        returning a L{Deferred} which fires with C{None} properly passes
        </nil> over the network if allowNone is set to True.
        """
        d = self.proxy().callRemote('defer', None)
        d.addCallback(self.assertEquals, None)
        return d


    def test_dictWithNoneValue(self):
        """
        Test that return a C{dict} with C{None} as a value works properly.
        """
        d = self.proxy().callRemote('defer', {'a': None})
        d.addCallback(self.assertEquals, {'a': None})
        return d



class XMLRPCTestAuthenticated(XMLRPCTestCase):
    """
    Test with authenticated proxy. We run this with the same inout/ouput as
    above.
    """
    user = "username"
    password = "asecret"

    def setUp(self):
        self.p = reactor.listenTCP(0, server.Site(TestAuthHeader()),
                                   interface="127.0.0.1")
        self.port = self.p.getHost().port
        self.factories = []


    def test_authInfoInURL(self):
        p = xmlrpc.Proxy("http://%s:%s@127.0.0.1:%d/" % (
            self.user, self.password, self.port))
        d = p.callRemote("authinfo")
        d.addCallback(self.assertEquals, [self.user, self.password])
        return d


    def test_explicitAuthInfo(self):
        p = xmlrpc.Proxy("http://127.0.0.1:%d/" % (
            self.port,), self.user, self.password)
        d = p.callRemote("authinfo")
        d.addCallback(self.assertEquals, [self.user, self.password])
        return d


    def test_explicitAuthInfoOverride(self):
        p = xmlrpc.Proxy("http://wrong:info@127.0.0.1:%d/" % (
                self.port,), self.user, self.password)
        d = p.callRemote("authinfo")
        d.addCallback(self.assertEquals, [self.user, self.password])
        return d


class XMLRPCTestIntrospection(XMLRPCTestCase):

    def setUp(self):
        xmlrpc = Test()
        addIntrospection(xmlrpc)
        self.p = reactor.listenTCP(0, server.Site(xmlrpc),interface="127.0.0.1")
        self.port = self.p.getHost().port
        self.factories = []

    def test_listMethods(self):

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

    def test_methodHelp(self):
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

    def test_methodSignature(self):
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


class XMLRPCClientErrorHandling(unittest.TestCase):
    """
    Test error handling on the xmlrpc client.
    """
    def setUp(self):
        self.resource = static.File(__file__)
        self.resource.isLeaf = True
        self.port = reactor.listenTCP(0, server.Site(self.resource),
                                                     interface='127.0.0.1')

    def tearDown(self):
        return self.port.stopListening()

    def test_erroneousResponse(self):
        """
        Test that calling the xmlrpc client on a static http server raises
        an exception.
        """
        proxy = xmlrpc.Proxy("http://127.0.0.1:%d/" %
                             (self.port.getHost().port,))
        return self.assertFailure(proxy.callRemote("someMethod"), Exception)

