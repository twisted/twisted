# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web._newclient}.
"""

__metaclass__ = type

from zope.interface import implements
from zope.interface.verify import verifyObject

from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet.interfaces import IConsumer, IPushProducer
from twisted.internet.error import ConnectionDone, ConnectionLost
from twisted.internet.defer import Deferred, succeed, fail
from twisted.internet.protocol import Protocol
from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import StringTransport, AccumulatingProtocol
from twisted.web._newclient import UNKNOWN_LENGTH, STATUS, HEADER, BODY, DONE
from twisted.web._newclient import Request, Response, HTTPParser, HTTPClientParser
from twisted.web._newclient import BadResponseVersion, ParseError, HTTP11ClientProtocol
from twisted.web._newclient import ChunkedEncoder, RequestGenerationFailed
from twisted.web._newclient import RequestTransmissionFailed, ResponseFailed
from twisted.web._newclient import WrongBodyLength, RequestNotSent
from twisted.web._newclient import ConnectionAborted, ResponseNeverReceived
from twisted.web._newclient import BadHeaders, ResponseDone, PotentialDataLoss, ExcessWrite
from twisted.web._newclient import TransportProxyProducer, LengthEnforcingConsumer, makeStatefulDispatcher
from twisted.web._newclient import NoBodyResponseDone
from twisted.web.http_headers import Headers
from twisted.web.http import _DataLoss
from twisted.web.iweb import IBodyProducer, IResponse



class ArbitraryException(Exception):
    """
    A unique, arbitrary exception type which L{twisted.web._newclient} knows
    nothing about.
    """


class AnotherArbitraryException(Exception):
    """
    Similar to L{ArbitraryException} but with a different identity.
    """


# A re-usable Headers instance for tests which don't really care what headers
# they're sending.
_boringHeaders = Headers({'host': ['example.com']})


def assertWrapperExceptionTypes(self, deferred, mainType, reasonTypes):
    """
    Assert that the given L{Deferred} fails with the exception given by
    C{mainType} and that the exceptions wrapped by the instance of C{mainType}
    it fails with match the list of exception types given by C{reasonTypes}.

    This is a helper for testing failures of exceptions which subclass
    L{_newclient._WrapperException}.

    @param self: A L{TestCase} instance which will be used to make the
        assertions.

    @param deferred: The L{Deferred} which is expected to fail with
        C{mainType}.

    @param mainType: A L{_newclient._WrapperException} subclass which will be
        trapped on C{deferred}.

    @param reasonTypes: A sequence of exception types which will be trapped on
        the resulting L{mainType} exception instance's C{reasons} sequence.

    @return: A L{Deferred} which fires with the C{mainType} instance
        C{deferred} fails with, or which fails somehow.
    """
    def cbFailed(err):
        for reason, type in zip(err.reasons, reasonTypes):
            reason.trap(type)
        self.assertEqual(len(err.reasons), len(reasonTypes),
                         "len(%s) != len(%s)" % (err.reasons, reasonTypes))
        return err
    d = self.assertFailure(deferred, mainType)
    d.addCallback(cbFailed)
    return d



def assertResponseFailed(self, deferred, reasonTypes):
    """
    A simple helper to invoke L{assertWrapperExceptionTypes} with a C{mainType}
    of L{ResponseFailed}.
    """
    return assertWrapperExceptionTypes(self, deferred, ResponseFailed, reasonTypes)



def assertRequestGenerationFailed(self, deferred, reasonTypes):
    """
    A simple helper to invoke L{assertWrapperExceptionTypes} with a C{mainType}
    of L{RequestGenerationFailed}.
    """
    return assertWrapperExceptionTypes(self, deferred, RequestGenerationFailed, reasonTypes)



def assertRequestTransmissionFailed(self, deferred, reasonTypes):
    """
    A simple helper to invoke L{assertWrapperExceptionTypes} with a C{mainType}
    of L{RequestTransmissionFailed}.
    """
    return assertWrapperExceptionTypes(self, deferred, RequestTransmissionFailed, reasonTypes)



def justTransportResponse(transport):
    """
    Helper function for creating a Response which uses the given transport.
    All of the other parameters to L{Response.__init__} are filled with
    arbitrary values.  Only use this method if you don't care about any of
    them.
    """
    return Response(('HTTP', 1, 1), 200, 'OK', _boringHeaders, transport)


class MakeStatefulDispatcherTests(TestCase):
    """
    Tests for L{makeStatefulDispatcher}.
    """
    def test_functionCalledByState(self):
        """
        A method defined with L{makeStatefulDispatcher} invokes a second
        method based on the current state of the object.
        """
        class Foo:
            _state = 'A'

            def bar(self):
                pass
            bar = makeStatefulDispatcher('quux', bar)

            def _quux_A(self):
                return 'a'

            def _quux_B(self):
                return 'b'

        stateful = Foo()
        self.assertEqual(stateful.bar(), 'a')
        stateful._state = 'B'
        self.assertEqual(stateful.bar(), 'b')
        stateful._state = 'C'
        self.assertRaises(RuntimeError, stateful.bar)



class _HTTPParserTests(object):
    """
    Base test class for L{HTTPParser} which is responsible for the bulk of
    the task of parsing HTTP bytes.
    """
    sep = None

    def test_statusCallback(self):
        """
        L{HTTPParser} calls its C{statusReceived} method when it receives a
        status line.
        """
        status = []
        protocol = HTTPParser()
        protocol.statusReceived = status.append
        protocol.makeConnection(StringTransport())
        self.assertEqual(protocol.state, STATUS)
        protocol.dataReceived('HTTP/1.1 200 OK' + self.sep)
        self.assertEqual(status, ['HTTP/1.1 200 OK'])
        self.assertEqual(protocol.state, HEADER)


    def _headerTestSetup(self):
        header = {}
        protocol = HTTPParser()
        protocol.headerReceived = header.__setitem__
        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK' + self.sep)
        return header, protocol


    def test_headerCallback(self):
        """
        L{HTTPParser} calls its C{headerReceived} method when it receives a
        header.
        """
        header, protocol = self._headerTestSetup()
        protocol.dataReceived('X-Foo:bar' + self.sep)
        # Cannot tell it's not a continue header until the next line arrives
        # and is not a continuation
        protocol.dataReceived(self.sep)
        self.assertEqual(header, {'X-Foo': 'bar'})
        self.assertEqual(protocol.state, BODY)


    def test_continuedHeaderCallback(self):
        """
        If a header is split over multiple lines, L{HTTPParser} calls
        C{headerReceived} with the entire value once it is received.
        """
        header, protocol = self._headerTestSetup()
        protocol.dataReceived('X-Foo: bar' + self.sep)
        protocol.dataReceived(' baz' + self.sep)
        protocol.dataReceived('\tquux' + self.sep)
        protocol.dataReceived(self.sep)
        self.assertEqual(header, {'X-Foo': 'bar baz\tquux'})
        self.assertEqual(protocol.state, BODY)


    def test_fieldContentWhitespace(self):
        """
        Leading and trailing linear whitespace is stripped from the header
        value passed to the C{headerReceived} callback.
        """
        header, protocol = self._headerTestSetup()
        value = ' \t %(sep)s bar \t%(sep)s \t%(sep)s' % dict(sep=self.sep)
        protocol.dataReceived('X-Bar:' + value)
        protocol.dataReceived('X-Foo:' + value)
        protocol.dataReceived(self.sep)
        self.assertEqual(header, {'X-Foo': 'bar',
                                  'X-Bar': 'bar'})


    def test_allHeadersCallback(self):
        """
        After the last header is received, L{HTTPParser} calls
        C{allHeadersReceived}.
        """
        called = []
        header, protocol = self._headerTestSetup()
        def allHeadersReceived():
            called.append(protocol.state)
            protocol.state = STATUS
        protocol.allHeadersReceived = allHeadersReceived
        protocol.dataReceived(self.sep)
        self.assertEqual(called, [HEADER])
        self.assertEqual(protocol.state, STATUS)


    def test_noHeaderCallback(self):
        """
        If there are no headers in the message, L{HTTPParser} does not call
        C{headerReceived}.
        """
        header, protocol = self._headerTestSetup()
        protocol.dataReceived(self.sep)
        self.assertEqual(header, {})
        self.assertEqual(protocol.state, BODY)


    def test_headersSavedOnResponse(self):
        """
        All headers received by L{HTTPParser} are added to
        L{HTTPParser.headers}.
        """
        protocol = HTTPParser()
        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK' + self.sep)
        protocol.dataReceived('X-Foo: bar' + self.sep)
        protocol.dataReceived('X-Foo: baz' + self.sep)
        protocol.dataReceived(self.sep)
        expected = [('X-Foo', ['bar', 'baz'])]
        self.assertEqual(expected, list(protocol.headers.getAllRawHeaders()))


    def test_connectionControlHeaders(self):
        """
        L{HTTPParser.isConnectionControlHeader} returns C{True} for headers
        which are always connection control headers (similar to "hop-by-hop"
        headers from RFC 2616 section 13.5.1) and C{False} for other headers.
        """
        protocol = HTTPParser()
        connHeaderNames = [
            'content-length', 'connection', 'keep-alive', 'te', 'trailers',
            'transfer-encoding', 'upgrade', 'proxy-connection']

        for header in connHeaderNames:
            self.assertTrue(
                protocol.isConnectionControlHeader(header),
                "Expecting %r to be a connection control header, but "
                "wasn't" % (header,))
        self.assertFalse(
            protocol.isConnectionControlHeader("date"),
            "Expecting the arbitrarily selected 'date' header to not be "
            "a connection control header, but was.")


    def test_switchToBodyMode(self):
        """
        L{HTTPParser.switchToBodyMode} raises L{RuntimeError} if called more
        than once.
        """
        protocol = HTTPParser()
        protocol.makeConnection(StringTransport())
        protocol.switchToBodyMode(object())
        self.assertRaises(RuntimeError, protocol.switchToBodyMode, object())



class HTTPParserTestsRFCComplaintDelimeter(_HTTPParserTests, TestCase):
    """
    L{_HTTPParserTests} using standard CR LF newlines.
    """
    sep = '\r\n'



class HTTPParserTestsNonRFCComplaintDelimeter(_HTTPParserTests, TestCase):
    """
    L{_HTTPParserTests} using bare LF newlines.
    """
    sep = '\n'



class HTTPClientParserTests(TestCase):
    """
    Tests for L{HTTPClientParser} which is responsible for parsing HTTP
    response messages.
    """
    def test_parseVersion(self):
        """
        L{HTTPClientParser.parseVersion} parses a status line into its three
        components.
        """
        protocol = HTTPClientParser(None, None)
        self.assertEqual(
            protocol.parseVersion('CANDY/7.2'),
            ('CANDY', 7, 2))


    def test_parseBadVersion(self):
        """
        L{HTTPClientParser.parseVersion} raises L{ValueError} when passed an
        unparsable version.
        """
        protocol = HTTPClientParser(None, None)
        e = BadResponseVersion
        f = protocol.parseVersion

        def checkParsing(s):
            exc = self.assertRaises(e, f, s)
            self.assertEqual(exc.data, s)

        checkParsing('foo')
        checkParsing('foo/bar/baz')

        checkParsing('foo/')
        checkParsing('foo/..')

        checkParsing('foo/a.b')
        checkParsing('foo/-1.-1')


    def test_responseStatusParsing(self):
        """
        L{HTTPClientParser.statusReceived} parses the version, code, and phrase
        from the status line and stores them on the response object.
        """
        request = Request('GET', '/', _boringHeaders, None)
        protocol = HTTPClientParser(request, None)
        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')
        self.assertEqual(protocol.response.version, ('HTTP', 1, 1))
        self.assertEqual(protocol.response.code, 200)
        self.assertEqual(protocol.response.phrase, 'OK')


    def test_badResponseStatus(self):
        """
        L{HTTPClientParser.statusReceived} raises L{ParseError} if it is called
        with a status line which cannot be parsed.
        """
        protocol = HTTPClientParser(None, None)

        def checkParsing(s):
            exc = self.assertRaises(ParseError, protocol.statusReceived, s)
            self.assertEqual(exc.data, s)

        # If there are fewer than three whitespace-delimited parts to the
        # status line, it is not valid and cannot be parsed.
        checkParsing('foo')
        checkParsing('HTTP/1.1 200')

        # If the response code is not an integer, the status line is not valid
        # and cannot be parsed.
        checkParsing('HTTP/1.1 bar OK')


    def _noBodyTest(self, request, status, response):
        """
        Assert that L{HTTPClientParser} parses the given C{response} to
        C{request}, resulting in a response with no body and no extra bytes and
        leaving the transport in the producing state.

        @param request: A L{Request} instance which might have caused a server
            to return the given response.
        @param status: A string giving the status line of the response to be
            parsed.
        @param response: A string giving the response to be parsed.

        @return: A C{dict} of headers from the response.
        """
        header = {}
        finished = []
        reason = []
        protocol = HTTPClientParser(request, finished.append)
        protocol.headerReceived = header.__setitem__
        body = []
        transport = StringTransport()
        protocol.makeConnection(transport)
        protocol.dataReceived(status)

        class StubConsumer(Protocol):
            def __init__(self, reason):
                self.reason = reason

            def dataReceived(self, data):
                pass

            def connectionLost(self, failure=None):
                if failure:
                    self.reason.append(failure.value)

        consumer = StubConsumer(reason)
        protocol.response.deliverBody(consumer)
        protocol.response._bodyDataReceived = body.append

        protocol.dataReceived(response)
        self.assertEqual(transport.producerState, 'producing')
        self.assertEqual(protocol.state, DONE)
        self.assertEqual(body, [])
        self.assertEqual(finished, [''])
        self.assertEqual(len(reason), 1)
        self.assertIsInstance(reason[0], NoBodyResponseDone)
        self.assertEqual(protocol.response.length, 0)
        return header


    def test_headResponse(self):
        """
        If the response is to a HEAD request, no body is expected, the body
        callback is not invoked, and the I{Content-Length} header is passed to
        the header callback.
        """
        request = Request('HEAD', '/', _boringHeaders, None)
        status = 'HTTP/1.1 200 OK\r\n'
        response = (
            'Content-Length: 10\r\n'
            '\r\n')
        header = self._noBodyTest(request, status, response)
        self.assertEqual(header, {'Content-Length': '10'})


    def test_noContentResponse(self):
        """
        If the response code is I{NO CONTENT} (204), no body is expected and
        the body callback is not invoked.
        """
        request = Request('GET', '/', _boringHeaders, None)
        status = 'HTTP/1.1 204 NO CONTENT\r\n'
        response = '\r\n'
        self._noBodyTest(request, status, response)


    def test_notModifiedResponse(self):
        """
        If the response code is I{NOT MODIFIED} (304), no body is expected and
        the body callback is not invoked.
        """
        request = Request('GET', '/', _boringHeaders, None)
        status = 'HTTP/1.1 304 NOT MODIFIED\r\n'
        response = '\r\n'
        self._noBodyTest(request, status, response)


    def test_responseHeaders(self):
        """
        The response headers are added to the response object's C{headers}
        L{Headers} instance.
        """
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None),
            lambda rest: None)
        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')
        protocol.dataReceived('X-Foo: bar\r\n')
        protocol.dataReceived('\r\n')
        self.assertEqual(
            protocol.connHeaders,
            Headers({}))
        self.assertEqual(
            protocol.response.headers,
            Headers({'x-foo': ['bar']}))
        self.assertIdentical(protocol.response.length, UNKNOWN_LENGTH)


    def test_connectionHeaders(self):
        """
        The connection control headers are added to the parser's C{connHeaders}
        L{Headers} instance.
        """
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None),
            lambda rest: None)
        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')
        protocol.dataReceived('Content-Length: 123\r\n')
        protocol.dataReceived('Connection: close\r\n')
        protocol.dataReceived('\r\n')
        self.assertEqual(
            protocol.response.headers,
            Headers({}))
        self.assertEqual(
            protocol.connHeaders,
            Headers({'content-length': ['123'],
                     'connection': ['close']}))
        self.assertEqual(protocol.response.length, 123)


    def test_headResponseContentLengthEntityHeader(self):
        """
        If a HEAD request is made, the I{Content-Length} header in the response
        is added to the response headers, not the connection control headers.
        """
        protocol = HTTPClientParser(
            Request('HEAD', '/', _boringHeaders, None),
            lambda rest: None)
        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')
        protocol.dataReceived('Content-Length: 123\r\n')
        protocol.dataReceived('\r\n')
        self.assertEqual(
            protocol.response.headers,
            Headers({'content-length': ['123']}))
        self.assertEqual(
            protocol.connHeaders,
            Headers({}))
        self.assertEqual(protocol.response.length, 0)


    def test_contentLength(self):
        """
        If a response includes a body with a length given by the
        I{Content-Length} header, the bytes which make up the body are passed
        to the C{_bodyDataReceived} callback on the L{HTTPParser}.
        """
        finished = []
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None),
            finished.append)
        transport = StringTransport()
        protocol.makeConnection(transport)
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')
        body = []
        protocol.response._bodyDataReceived = body.append
        protocol.dataReceived('Content-Length: 10\r\n')
        protocol.dataReceived('\r\n')

        # Incidentally, the transport should be paused now.  It is the response
        # object's responsibility to resume this when it is ready for bytes.
        self.assertEqual(transport.producerState, 'paused')

        self.assertEqual(protocol.state, BODY)
        protocol.dataReceived('x' * 6)
        self.assertEqual(body, ['x' * 6])
        self.assertEqual(protocol.state, BODY)
        protocol.dataReceived('y' * 4)
        self.assertEqual(body, ['x' * 6, 'y' * 4])
        self.assertEqual(protocol.state, DONE)
        self.assertTrue(finished, [''])


    def test_zeroContentLength(self):
        """
        If a response includes a I{Content-Length} header indicating zero bytes
        in the response, L{Response.length} is set accordingly and no data is
        delivered to L{Response._bodyDataReceived}.
        """
        finished = []
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None),
            finished.append)

        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')

        body = []
        protocol.response._bodyDataReceived = body.append

        protocol.dataReceived('Content-Length: 0\r\n')
        protocol.dataReceived('\r\n')

        self.assertEqual(protocol.state, DONE)
        self.assertEqual(body, [])
        self.assertTrue(finished, [''])
        self.assertEqual(protocol.response.length, 0)



    def test_multipleContentLengthHeaders(self):
        """
        If a response includes multiple I{Content-Length} headers,
        L{HTTPClientParser.dataReceived} raises L{ValueError} to indicate that
        the response is invalid and the transport is now unusable.
        """
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None),
            None)

        protocol.makeConnection(StringTransport())
        self.assertRaises(
            ValueError,
            protocol.dataReceived,
            'HTTP/1.1 200 OK\r\n'
            'Content-Length: 1\r\n'
            'Content-Length: 2\r\n'
            '\r\n')


    def test_extraBytesPassedBack(self):
        """
        If extra bytes are received past the end of a response, they are passed
        to the finish callback.
        """
        finished = []
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None),
            finished.append)

        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')
        protocol.dataReceived('Content-Length: 0\r\n')
        protocol.dataReceived('\r\nHere is another thing!')
        self.assertEqual(protocol.state, DONE)
        self.assertEqual(finished, ['Here is another thing!'])


    def test_extraBytesPassedBackHEAD(self):
        """
        If extra bytes are received past the end of the headers of a response
        to a HEAD request, they are passed to the finish callback.
        """
        finished = []
        protocol = HTTPClientParser(
            Request('HEAD', '/', _boringHeaders, None),
            finished.append)

        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')
        protocol.dataReceived('Content-Length: 12\r\n')
        protocol.dataReceived('\r\nHere is another thing!')
        self.assertEqual(protocol.state, DONE)
        self.assertEqual(finished, ['Here is another thing!'])


    def test_chunkedResponseBody(self):
        """
        If the response headers indicate the response body is encoded with the
        I{chunked} transfer encoding, the body is decoded according to that
        transfer encoding before being passed to L{Response._bodyDataReceived}.
        """
        finished = []
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None),
            finished.append)
        protocol.makeConnection(StringTransport())
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')

        body = []
        protocol.response._bodyDataReceived = body.append

        protocol.dataReceived('Transfer-Encoding: chunked\r\n')
        protocol.dataReceived('\r\n')

        # No data delivered yet
        self.assertEqual(body, [])

        # Cannot predict the length of a chunked encoded response body.
        self.assertIdentical(protocol.response.length, UNKNOWN_LENGTH)

        # Deliver some chunks and make sure the data arrives
        protocol.dataReceived('3\r\na')
        self.assertEqual(body, ['a'])
        protocol.dataReceived('bc\r\n')
        self.assertEqual(body, ['a', 'bc'])

        # The response's _bodyDataFinished method should be called when the last
        # chunk is received.  Extra data should be passed to the finished
        # callback.
        protocol.dataReceived('0\r\n\r\nextra')
        self.assertEqual(finished, ['extra'])


    def test_unknownContentLength(self):
        """
        If a response does not include a I{Transfer-Encoding} or a
        I{Content-Length}, the end of response body is indicated by the
        connection being closed.
        """
        finished = []
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None), finished.append)
        transport = StringTransport()
        protocol.makeConnection(transport)
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')

        body = []
        protocol.response._bodyDataReceived = body.append

        protocol.dataReceived('\r\n')
        protocol.dataReceived('foo')
        protocol.dataReceived('bar')
        self.assertEqual(body, ['foo', 'bar'])
        protocol.connectionLost(ConnectionDone("simulated end of connection"))
        self.assertEqual(finished, [''])


    def test_contentLengthAndTransferEncoding(self):
        """
        According to RFC 2616, section 4.4, point 3, if I{Content-Length} and
        I{Transfer-Encoding: chunked} are present, I{Content-Length} MUST be
        ignored
        """
        finished = []
        protocol = HTTPClientParser(
            Request('GET', '/', _boringHeaders, None), finished.append)
        transport = StringTransport()
        protocol.makeConnection(transport)
        protocol.dataReceived('HTTP/1.1 200 OK\r\n')

        body = []
        protocol.response._bodyDataReceived = body.append

        protocol.dataReceived(
            'Content-Length: 102\r\n'
            'Transfer-Encoding: chunked\r\n'
            '\r\n'
            '3\r\n'
            'abc\r\n'
            '0\r\n'
            '\r\n')

        self.assertEqual(body, ['abc'])
        self.assertEqual(finished, [''])


    def test_connectionLostBeforeBody(self):
        """
        If L{HTTPClientParser.connectionLost} is called before the headers are
        finished, the C{_responseDeferred} is fired with the L{Failure} passed
        to C{connectionLost}.
        """
        transport = StringTransport()
        protocol = HTTPClientParser(Request('GET', '/', _boringHeaders, None), None)
        protocol.makeConnection(transport)
        # Grab this here because connectionLost gets rid of the attribute
        responseDeferred = protocol._responseDeferred
        protocol.connectionLost(Failure(ArbitraryException()))

        return assertResponseFailed(
            self, responseDeferred, [ArbitraryException])


    def test_connectionLostWithError(self):
        """
        If one of the L{Response} methods called by
        L{HTTPClientParser.connectionLost} raises an exception, the exception
        is logged and not re-raised.
        """
        transport = StringTransport()
        protocol = HTTPClientParser(Request('GET', '/', _boringHeaders, None),
                                    None)
        protocol.makeConnection(transport)

        response = []
        protocol._responseDeferred.addCallback(response.append)
        protocol.dataReceived(
            'HTTP/1.1 200 OK\r\n'
            'Content-Length: 1\r\n'
            '\r\n')
        response = response[0]

        # Arrange for an exception
        def fakeBodyDataFinished(err=None):
            raise ArbitraryException()
        response._bodyDataFinished = fakeBodyDataFinished

        protocol.connectionLost(None)

        self.assertEqual(len(self.flushLoggedErrors(ArbitraryException)), 1)


    def test_noResponseAtAll(self):
        """
        If no response at all was received and the connection is lost, the
        resulting error is L{ResponseNeverReceived}.
        """
        protocol = HTTPClientParser(
            Request('HEAD', '/', _boringHeaders, None),
            lambda ign: None)
        d = protocol._responseDeferred

        protocol.makeConnection(StringTransport())
        protocol.connectionLost(ConnectionLost())
        return self.assertFailure(d, ResponseNeverReceived)


    def test_someResponseButNotAll(self):
        """
        If a partial response was received and the connection is lost, the
        resulting error is L{ResponseFailed}, but not
        L{ResponseNeverReceived}.
        """
        protocol = HTTPClientParser(
            Request('HEAD', '/', _boringHeaders, None),
            lambda ign: None)
        d = protocol._responseDeferred

        protocol.makeConnection(StringTransport())
        protocol.dataReceived('2')
        protocol.connectionLost(ConnectionLost())
        return self.assertFailure(d, ResponseFailed).addCallback(
            self.assertIsInstance, ResponseFailed)



class SlowRequest:
    """
    L{SlowRequest} is a fake implementation of L{Request} which is easily
    controlled externally (for example, by code in a test method).

    @ivar stopped: A flag indicating whether C{stopWriting} has been called.

    @ivar finished: After C{writeTo} is called, a L{Deferred} which was
        returned by that method.  L{SlowRequest} will never fire this
        L{Deferred}.
    """
    method = 'GET'
    stopped = False
    persistent = False

    def writeTo(self, transport):
        self.finished = Deferred()
        return self.finished


    def stopWriting(self):
        self.stopped = True



class SimpleRequest:
    """
    L{SimpleRequest} is a fake implementation of L{Request} which writes a
    short, fixed string to the transport passed to its C{writeTo} method and
    returns a succeeded L{Deferred}.  This vaguely emulates the behavior of a
    L{Request} with no body producer.
    """
    persistent = False

    def writeTo(self, transport):
        transport.write('SOME BYTES')
        return succeed(None)



class HTTP11ClientProtocolTests(TestCase):
    """
    Tests for the HTTP 1.1 client protocol implementation,
    L{HTTP11ClientProtocol}.
    """
    def setUp(self):
        """
        Create an L{HTTP11ClientProtocol} connected to a fake transport.
        """
        self.transport = StringTransport()
        self.protocol = HTTP11ClientProtocol()
        self.protocol.makeConnection(self.transport)


    def test_request(self):
        """
        L{HTTP11ClientProtocol.request} accepts a L{Request} and calls its
        C{writeTo} method with its own transport.
        """
        self.protocol.request(SimpleRequest())
        self.assertEqual(self.transport.value(), 'SOME BYTES')


    def test_secondRequest(self):
        """
        The second time L{HTTP11ClientProtocol.request} is called, it returns a
        L{Deferred} which immediately fires with a L{Failure} wrapping a
        L{RequestNotSent} exception.
        """
        self.protocol.request(SlowRequest())
        def cbNotSent(ignored):
            self.assertEqual(self.transport.value(), '')
        d = self.assertFailure(
            self.protocol.request(SimpleRequest()), RequestNotSent)
        d.addCallback(cbNotSent)
        return d


    def test_requestAfterConnectionLost(self):
        """
        L{HTTP11ClientProtocol.request} returns a L{Deferred} which immediately
        fires with a L{Failure} wrapping a L{RequestNotSent} if called after
        the protocol has been disconnected.
        """
        self.protocol.connectionLost(
            Failure(ConnectionDone("sad transport")))
        def cbNotSent(ignored):
            self.assertEqual(self.transport.value(), '')
        d = self.assertFailure(
            self.protocol.request(SimpleRequest()), RequestNotSent)
        d.addCallback(cbNotSent)
        return d


    def test_failedWriteTo(self):
        """
        If the L{Deferred} returned by L{Request.writeTo} fires with a
        L{Failure}, L{HTTP11ClientProtocol.request} disconnects its transport
        and returns a L{Deferred} which fires with a L{Failure} of
        L{RequestGenerationFailed} wrapping the underlying failure.
        """
        class BrokenRequest:
            persistent = False
            def writeTo(self, transport):
                return fail(ArbitraryException())

        d = self.protocol.request(BrokenRequest())
        def cbFailed(ignored):
            self.assertTrue(self.transport.disconnecting)
            # Simulate what would happen if the protocol had a real transport
            # and make sure no exception is raised.
            self.protocol.connectionLost(
                Failure(ConnectionDone("you asked for it")))
        d = assertRequestGenerationFailed(self, d, [ArbitraryException])
        d.addCallback(cbFailed)
        return d


    def test_synchronousWriteToError(self):
        """
        If L{Request.writeTo} raises an exception,
        L{HTTP11ClientProtocol.request} returns a L{Deferred} which fires with
        a L{Failure} of L{RequestGenerationFailed} wrapping that exception.
        """
        class BrokenRequest:
            persistent = False
            def writeTo(self, transport):
                raise ArbitraryException()

        d = self.protocol.request(BrokenRequest())
        return assertRequestGenerationFailed(self, d, [ArbitraryException])


    def test_connectionLostDuringRequestGeneration(self, mode=None):
        """
        If L{HTTP11ClientProtocol}'s transport is disconnected before the
        L{Deferred} returned by L{Request.writeTo} fires, the L{Deferred}
        returned by L{HTTP11ClientProtocol.request} fires with a L{Failure} of
        L{RequestTransmissionFailed} wrapping the underlying failure.
        """
        request = SlowRequest()
        d = self.protocol.request(request)
        d = assertRequestTransmissionFailed(self, d, [ArbitraryException])

        # The connection hasn't been lost yet.  The request should still be
        # allowed to do its thing.
        self.assertFalse(request.stopped)

        self.protocol.connectionLost(Failure(ArbitraryException()))

        # Now the connection has been lost.  The request should have been told
        # to stop writing itself.
        self.assertTrue(request.stopped)

        if mode == 'callback':
            request.finished.callback(None)
        elif mode == 'errback':
            request.finished.errback(Failure(AnotherArbitraryException()))
            errors = self.flushLoggedErrors(AnotherArbitraryException)
            self.assertEqual(len(errors), 1)
        else:
            # Don't fire the writeTo Deferred at all.
            pass
        return d


    def test_connectionLostBeforeGenerationFinished(self):
        """
        If the request passed to L{HTTP11ClientProtocol} finishes generation
        successfully after the L{HTTP11ClientProtocol}'s connection has been
        lost, nothing happens.
        """
        return self.test_connectionLostDuringRequestGeneration('callback')


    def test_connectionLostBeforeGenerationFailed(self):
        """
        If the request passed to L{HTTP11ClientProtocol} finished generation
        with an error after the L{HTTP11ClientProtocol}'s connection has been
        lost, nothing happens.
        """
        return self.test_connectionLostDuringRequestGeneration('errback')


    def test_errorMessageOnConnectionLostBeforeGenerationFailedDoesNotConfuse(self):
        """
        If the request passed to L{HTTP11ClientProtocol} finished generation
        with an error after the L{HTTP11ClientProtocol}'s connection has been
        lost, an error is logged that gives a non-confusing hint to user on what
        went wrong.
        """
        errors = []
        log.addObserver(errors.append)
        self.addCleanup(log.removeObserver, errors.append)

        def check(ignore):
            error = errors[0]
            self.assertEqual(error['why'],
                              'Error writing request, but not in valid state '
                              'to finalize request: CONNECTION_LOST')

        return self.test_connectionLostDuringRequestGeneration(
            'errback').addCallback(check)


    def test_receiveSimplestResponse(self):
        """
        When a response is delivered to L{HTTP11ClientProtocol}, the
        L{Deferred} previously returned by the C{request} method is called back
        with a L{Response} instance and the connection is closed.
        """
        d = self.protocol.request(Request('GET', '/', _boringHeaders, None))
        def cbRequest(response):
            self.assertEqual(response.code, 200)
            self.assertEqual(response.headers, Headers())
            self.assertTrue(self.transport.disconnecting)
            self.assertEqual(self.protocol.state, 'QUIESCENT')
        d.addCallback(cbRequest)
        self.protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n"
            "\r\n")
        return d


    def test_receiveResponseHeaders(self):
        """
        The headers included in a response delivered to L{HTTP11ClientProtocol}
        are included on the L{Response} instance passed to the callback
        returned by the C{request} method.
        """
        d = self.protocol.request(Request('GET', '/', _boringHeaders, None))
        def cbRequest(response):
            expected = Headers({'x-foo': ['bar', 'baz']})
            self.assertEqual(response.headers, expected)
        d.addCallback(cbRequest)
        self.protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "X-Foo: bar\r\n"
            "X-Foo: baz\r\n"
            "\r\n")
        return d


    def test_receiveResponseBeforeRequestGenerationDone(self):
        """
        If response bytes are delivered to L{HTTP11ClientProtocol} before the
        L{Deferred} returned by L{Request.writeTo} fires, those response bytes
        are parsed as part of the response.

        The connection is also closed, because we're in a confusing state, and
        therefore the C{quiescentCallback} isn't called.
        """
        quiescentResult = []
        transport = StringTransport()
        protocol = HTTP11ClientProtocol(quiescentResult.append)
        protocol.makeConnection(transport)

        request = SlowRequest()
        d = protocol.request(request)
        protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "X-Foo: bar\r\n"
            "Content-Length: 6\r\n"
            "\r\n"
            "foobar")
        def cbResponse(response):
            p = AccumulatingProtocol()
            whenFinished = p.closedDeferred = Deferred()
            response.deliverBody(p)
            self.assertEqual(
                protocol.state, 'TRANSMITTING_AFTER_RECEIVING_RESPONSE')
            self.assertTrue(transport.disconnecting)
            self.assertEqual(quiescentResult, [])
            return whenFinished.addCallback(
                lambda ign: (response, p.data))
        d.addCallback(cbResponse)
        def cbAllResponse((response, body)):
            self.assertEqual(response.version, ('HTTP', 1, 1))
            self.assertEqual(response.code, 200)
            self.assertEqual(response.phrase, 'OK')
            self.assertEqual(response.headers, Headers({'x-foo': ['bar']}))
            self.assertEqual(body, "foobar")

            # Also nothing bad should happen if the request does finally
            # finish, even though it is completely irrelevant.
            request.finished.callback(None)

        d.addCallback(cbAllResponse)
        return d


    def test_connectionLostAfterReceivingResponseBeforeRequestGenerationDone(self):
        """
        If response bytes are delivered to L{HTTP11ClientProtocol} before the
        request completes, calling L{connectionLost} on the protocol will
        result in protocol being moved to C{'CONNECTION_LOST'} state.
        """
        request = SlowRequest()
        d = self.protocol.request(request)
        self.protocol.dataReceived(
            "HTTP/1.1 400 BAD REQUEST\r\n"
            "Content-Length: 9\r\n"
            "\r\n"
            "tisk tisk")
        def cbResponse(response):
            p = AccumulatingProtocol()
            whenFinished = p.closedDeferred = Deferred()
            response.deliverBody(p)
            return whenFinished.addCallback(
                lambda ign: (response, p.data))
        d.addCallback(cbResponse)
        def cbAllResponse(ignore):
            request.finished.callback(None)
            # Nothing dire will happen when the connection is lost
            self.protocol.connectionLost(Failure(ArbitraryException()))
            self.assertEqual(self.protocol._state, 'CONNECTION_LOST')
        d.addCallback(cbAllResponse)
        return d


    def test_receiveResponseBody(self):
        """
        The C{deliverBody} method of the response object with which the
        L{Deferred} returned by L{HTTP11ClientProtocol.request} fires can be
        used to get the body of the response.
        """
        protocol = AccumulatingProtocol()
        whenFinished = protocol.closedDeferred = Deferred()
        requestDeferred = self.protocol.request(Request('GET', '/', _boringHeaders, None))

        self.protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-Length: 6\r\n"
            "\r")

        # Here's what's going on: all the response headers have been delivered
        # by this point, so the request Deferred can fire with a Response
        # object.  The body is yet to come, but that's okay, because the
        # Response object is how you *get* the body.
        result = []
        requestDeferred.addCallback(result.append)

        self.assertEqual(result, [])
        # Deliver the very last byte of the response.  It is exactly at this
        # point which the Deferred returned by request should fire.
        self.protocol.dataReceived("\n")
        response = result[0]

        response.deliverBody(protocol)

        self.protocol.dataReceived("foo")
        self.protocol.dataReceived("bar")

        def cbAllResponse(ignored):
            self.assertEqual(protocol.data, "foobar")
            protocol.closedReason.trap(ResponseDone)
        whenFinished.addCallback(cbAllResponse)
        return whenFinished


    def test_responseBodyFinishedWhenConnectionLostWhenContentLengthIsUnknown(
        self):
        """
        If the length of the response body is unknown, the protocol passed to
        the response's C{deliverBody} method has its C{connectionLost}
        method called with a L{Failure} wrapping a L{PotentialDataLoss}
        exception.
        """
        requestDeferred = self.protocol.request(Request('GET', '/', _boringHeaders, None))
        self.protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "\r\n")

        result = []
        requestDeferred.addCallback(result.append)
        response = result[0]

        protocol = AccumulatingProtocol()
        response.deliverBody(protocol)

        self.protocol.dataReceived("foo")
        self.protocol.dataReceived("bar")

        self.assertEqual(protocol.data, "foobar")
        self.protocol.connectionLost(
            Failure(ConnectionDone("low-level transport disconnected")))

        protocol.closedReason.trap(PotentialDataLoss)


    def test_chunkedResponseBodyUnfinishedWhenConnectionLost(self):
        """
        If the final chunk has not been received when the connection is lost
        (for any reason), the protocol passed to C{deliverBody} has its
        C{connectionLost} method called with a L{Failure} wrapping the
        exception for that reason.
        """
        requestDeferred = self.protocol.request(Request('GET', '/', _boringHeaders, None))
        self.protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Transfer-Encoding: chunked\r\n"
            "\r\n")

        result = []
        requestDeferred.addCallback(result.append)
        response = result[0]

        protocol = AccumulatingProtocol()
        response.deliverBody(protocol)

        self.protocol.dataReceived("3\r\nfoo\r\n")
        self.protocol.dataReceived("3\r\nbar\r\n")

        self.assertEqual(protocol.data, "foobar")

        self.protocol.connectionLost(Failure(ArbitraryException()))

        return assertResponseFailed(
            self, fail(protocol.closedReason), [ArbitraryException, _DataLoss])


    def test_parserDataReceivedException(self):
        """
        If the parser L{HTTP11ClientProtocol} delivers bytes to in
        C{dataReceived} raises an exception, the exception is wrapped in a
        L{Failure} and passed to the parser's C{connectionLost} and then the
        L{HTTP11ClientProtocol}'s transport is disconnected.
        """
        requestDeferred = self.protocol.request(Request('GET', '/', _boringHeaders, None))
        self.protocol.dataReceived('unparseable garbage goes here\r\n')
        d = assertResponseFailed(self, requestDeferred, [ParseError])
        def cbFailed(exc):
            self.assertTrue(self.transport.disconnecting)
            self.assertEqual(
                exc.reasons[0].value.data, 'unparseable garbage goes here')

            # Now do what StringTransport doesn't do but a real transport would
            # have, call connectionLost on the HTTP11ClientProtocol.  Nothing
            # is asserted about this, but it's important for it to not raise an
            # exception.
            self.protocol.connectionLost(Failure(ConnectionDone("it is done")))

        d.addCallback(cbFailed)
        return d


    def test_proxyStopped(self):
        """
        When the HTTP response parser is disconnected, the
        L{TransportProxyProducer} which was connected to it as a transport is
        stopped.
        """
        requestDeferred = self.protocol.request(Request('GET', '/', _boringHeaders, None))
        transport = self.protocol._parser.transport
        self.assertIdentical(transport._producer, self.transport)
        self.protocol._disconnectParser(Failure(ConnectionDone("connection done")))
        self.assertIdentical(transport._producer, None)
        return assertResponseFailed(self, requestDeferred, [ConnectionDone])


    def test_abortClosesConnection(self):
        """
        L{HTTP11ClientProtocol.abort} will tell the transport to close its
        connection when it is invoked, and returns a C{Deferred} that fires
        when the connection is lost.
        """
        transport = StringTransport()
        protocol = HTTP11ClientProtocol()
        protocol.makeConnection(transport)
        r1 = []
        r2 = []
        protocol.abort().addCallback(r1.append)
        protocol.abort().addCallback(r2.append)
        self.assertEqual((r1, r2), ([], []))
        self.assertTrue(transport.disconnecting)

        # Disconnect protocol, the Deferreds will fire:
        protocol.connectionLost(Failure(ConnectionDone()))
        self.assertEqual(r1, [None])
        self.assertEqual(r2, [None])


    def test_abortAfterConnectionLost(self):
        """
        L{HTTP11ClientProtocol.abort} called after the connection is lost
        returns a C{Deferred} that fires immediately.
        """
        transport = StringTransport()
        protocol = HTTP11ClientProtocol()
        protocol.makeConnection(transport)
        protocol.connectionLost(Failure(ConnectionDone()))

        result = []
        protocol.abort().addCallback(result.append)
        self.assertEqual(result, [None])
        self.assertEqual(protocol._state, "CONNECTION_LOST")


    def test_abortBeforeResponseBody(self):
        """
        The Deferred returned by L{HTTP11ClientProtocol.request} will fire
        with a L{ResponseFailed} failure containing a L{ConnectionAborted}
        exception, if the connection was aborted before all response headers
        have been received.
        """
        transport = StringTransport()
        protocol = HTTP11ClientProtocol()
        protocol.makeConnection(transport)
        result = protocol.request(Request('GET', '/', _boringHeaders, None))
        protocol.abort()
        self.assertTrue(transport.disconnecting)
        protocol.connectionLost(Failure(ConnectionDone()))
        return assertResponseFailed(self, result, [ConnectionAborted])


    def test_abortAfterResponseHeaders(self):
        """
        When the connection is aborted after the response headers have
        been received and the L{Response} has been made available to
        application code, the response body protocol's C{connectionLost}
        method will be invoked with a L{ResponseFailed} failure containing a
        L{ConnectionAborted} exception.
        """
        transport = StringTransport()
        protocol = HTTP11ClientProtocol()
        protocol.makeConnection(transport)
        result = protocol.request(Request('GET', '/', _boringHeaders, None))

        protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-Length: 1\r\n"
            "\r\n"
            )

        testResult = Deferred()

        class BodyDestination(Protocol):
            """
            A body response protocol which immediately aborts the HTTP
            connection.
            """
            def connectionMade(self):
                """
                Abort the HTTP connection.
                """
                protocol.abort()

            def connectionLost(self, reason):
                """
                Make the reason for the losing of the connection available to
                the unit test via C{testResult}.
                """
                testResult.errback(reason)


        def deliverBody(response):
            """
            Connect the L{BodyDestination} response body protocol to the
            response, and then simulate connection loss after ensuring that
            the HTTP connection has been aborted.
            """
            response.deliverBody(BodyDestination())
            self.assertTrue(transport.disconnecting)
            protocol.connectionLost(Failure(ConnectionDone()))


        def checkError(error):
            self.assertIsInstance(error.response, Response)


        result.addCallback(deliverBody)
        deferred = assertResponseFailed(self, testResult,
                                        [ConnectionAborted, _DataLoss])
        return deferred.addCallback(checkError)


    def test_quiescentCallbackCalled(self):
        """
        If after a response is done the {HTTP11ClientProtocol} stays open and
        returns to QUIESCENT state, all per-request state is reset and the
        C{quiescentCallback} is called with the protocol instance.

        This is useful for implementing a persistent connection pool.

        The C{quiescentCallback} is called *before* the response-receiving
        protocol's C{connectionLost}, so that new requests triggered by end of
        first request can re-use a persistent connection.
        """
        quiescentResult = []
        def callback(p):
            self.assertEqual(p, protocol)
            self.assertEqual(p.state, "QUIESCENT")
            quiescentResult.append(p)

        transport = StringTransport()
        protocol = HTTP11ClientProtocol(callback)
        protocol.makeConnection(transport)

        requestDeferred = protocol.request(
            Request('GET', '/', _boringHeaders, None, persistent=True))
        protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-length: 3\r\n"
            "\r\n")

        # Headers done, but still no quiescent callback:
        self.assertEqual(quiescentResult, [])

        result = []
        requestDeferred.addCallback(result.append)
        response = result[0]

        # When response body is done (i.e. connectionLost is called), note the
        # fact in quiescentResult:
        bodyProtocol = AccumulatingProtocol()
        bodyProtocol.closedDeferred = Deferred()
        bodyProtocol.closedDeferred.addCallback(
            lambda ign: quiescentResult.append("response done"))

        response.deliverBody(bodyProtocol)
        protocol.dataReceived("abc")
        bodyProtocol.closedReason.trap(ResponseDone)
        # Quiescent callback called *before* protocol handling the response
        # body gets its connectionLost called:
        self.assertEqual(quiescentResult, [protocol, "response done"])

        # Make sure everything was cleaned up:
        self.assertEqual(protocol._parser, None)
        self.assertEqual(protocol._finishedRequest, None)
        self.assertEqual(protocol._currentRequest, None)
        self.assertEqual(protocol._transportProxy, None)
        self.assertEqual(protocol._responseDeferred, None)


    def test_quiescentCallbackCalledEmptyResponse(self):
        """
        The quiescentCallback is called before the request C{Deferred} fires,
        in cases where the response has no body.
        """
        quiescentResult = []
        def callback(p):
            self.assertEqual(p, protocol)
            self.assertEqual(p.state, "QUIESCENT")
            quiescentResult.append(p)

        transport = StringTransport()
        protocol = HTTP11ClientProtocol(callback)
        protocol.makeConnection(transport)

        requestDeferred = protocol.request(
            Request('GET', '/', _boringHeaders, None, persistent=True))
        requestDeferred.addCallback(quiescentResult.append)
        protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-length: 0\r\n"
            "\r\n")

        self.assertEqual(len(quiescentResult), 2)
        self.assertIdentical(quiescentResult[0], protocol)
        self.assertIsInstance(quiescentResult[1], Response)


    def test_quiescentCallbackNotCalled(self):
        """
        If after a response is done the {HTTP11ClientProtocol} returns a
        C{Connection: close} header in the response, the C{quiescentCallback}
        is not called and the connection is lost.
        """
        quiescentResult = []
        transport = StringTransport()
        protocol = HTTP11ClientProtocol(quiescentResult.append)
        protocol.makeConnection(transport)

        requestDeferred = protocol.request(
            Request('GET', '/', _boringHeaders, None, persistent=True))
        protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-length: 0\r\n"
            "Connection: close\r\n"
            "\r\n")

        result = []
        requestDeferred.addCallback(result.append)
        response = result[0]

        bodyProtocol = AccumulatingProtocol()
        response.deliverBody(bodyProtocol)
        bodyProtocol.closedReason.trap(ResponseDone)
        self.assertEqual(quiescentResult, [])
        self.assertTrue(transport.disconnecting)


    def test_quiescentCallbackNotCalledNonPersistentQuery(self):
        """
        If the request was non-persistent (i.e. sent C{Connection: close}),
        the C{quiescentCallback} is not called and the connection is lost.
        """
        quiescentResult = []
        transport = StringTransport()
        protocol = HTTP11ClientProtocol(quiescentResult.append)
        protocol.makeConnection(transport)

        requestDeferred = protocol.request(
            Request('GET', '/', _boringHeaders, None, persistent=False))
        protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-length: 0\r\n"
            "\r\n")

        result = []
        requestDeferred.addCallback(result.append)
        response = result[0]

        bodyProtocol = AccumulatingProtocol()
        response.deliverBody(bodyProtocol)
        bodyProtocol.closedReason.trap(ResponseDone)
        self.assertEqual(quiescentResult, [])
        self.assertTrue(transport.disconnecting)


    def test_quiescentCallbackThrows(self):
        """
        If C{quiescentCallback} throws an exception, the error is logged and
        protocol is disconnected.
        """
        def callback(p):
            raise ZeroDivisionError()

        transport = StringTransport()
        protocol = HTTP11ClientProtocol(callback)
        protocol.makeConnection(transport)

        requestDeferred = protocol.request(
            Request('GET', '/', _boringHeaders, None, persistent=True))
        protocol.dataReceived(
            "HTTP/1.1 200 OK\r\n"
            "Content-length: 0\r\n"
            "\r\n")

        result = []
        requestDeferred.addCallback(result.append)
        response = result[0]
        bodyProtocol = AccumulatingProtocol()
        response.deliverBody(bodyProtocol)
        bodyProtocol.closedReason.trap(ResponseDone)

        errors = self.flushLoggedErrors(ZeroDivisionError)
        self.assertEqual(len(errors), 1)
        self.assertTrue(transport.disconnecting)



class StringProducer:
    """
    L{StringProducer} is a dummy body producer.

    @ivar stopped: A flag which indicates whether or not C{stopProducing} has
        been called.
    @ivar consumer: After C{startProducing} is called, the value of the
        C{consumer} argument to that method.
    @ivar finished: After C{startProducing} is called, a L{Deferred} which was
        returned by that method.  L{StringProducer} will never fire this
        L{Deferred}.
    """
    implements(IBodyProducer)

    stopped = False

    def __init__(self, length):
        self.length = length


    def startProducing(self, consumer):
        self.consumer = consumer
        self.finished = Deferred()
        return self.finished


    def stopProducing(self):
        self.stopped = True



class RequestTests(TestCase):
    """
    Tests for L{Request}.
    """
    def setUp(self):
        self.transport = StringTransport()


    def test_sendSimplestRequest(self):
        """
        L{Request.writeTo} formats the request data and writes it to the given
        transport.
        """
        Request('GET', '/', _boringHeaders, None).writeTo(self.transport)
        self.assertEqual(
            self.transport.value(),
            "GET / HTTP/1.1\r\n"
            "Connection: close\r\n"
            "Host: example.com\r\n"
            "\r\n")


    def test_sendSimplestPersistentRequest(self):
        """
        A pesistent request does not send 'Connection: close' header.
        """
        req = Request('GET', '/', _boringHeaders, None, persistent=True)
        req.writeTo(self.transport)
        self.assertEqual(
            self.transport.value(),
            "GET / HTTP/1.1\r\n"
            "Host: example.com\r\n"
            "\r\n")


    def test_sendRequestHeaders(self):
        """
        L{Request.writeTo} formats header data and writes it to the given
        transport.
        """
        headers = Headers({'x-foo': ['bar', 'baz'], 'host': ['example.com']})
        Request('GET', '/foo', headers, None).writeTo(self.transport)
        lines = self.transport.value().split('\r\n')
        self.assertEqual(lines[0], "GET /foo HTTP/1.1")
        self.assertEqual(lines[-2:], ["", ""])
        del lines[0], lines[-2:]
        lines.sort()
        self.assertEqual(
            lines,
            ["Connection: close",
             "Host: example.com",
             "X-Foo: bar",
             "X-Foo: baz"])


    def test_sendChunkedRequestBody(self):
        """
        L{Request.writeTo} uses chunked encoding to write data from the request
        body producer to the given transport.  It registers the request body
        producer with the transport.
        """
        producer = StringProducer(UNKNOWN_LENGTH)
        request = Request('POST', '/bar', _boringHeaders, producer)
        request.writeTo(self.transport)

        self.assertNotIdentical(producer.consumer, None)
        self.assertIdentical(self.transport.producer, producer)
        self.assertTrue(self.transport.streaming)

        self.assertEqual(
            self.transport.value(),
            "POST /bar HTTP/1.1\r\n"
            "Connection: close\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Host: example.com\r\n"
            "\r\n")
        self.transport.clear()

        producer.consumer.write('x' * 3)
        producer.consumer.write('y' * 15)
        producer.finished.callback(None)
        self.assertIdentical(self.transport.producer, None)
        self.assertEqual(
            self.transport.value(),
            "3\r\n"
            "xxx\r\n"
            "f\r\n"
            "yyyyyyyyyyyyyyy\r\n"
            "0\r\n"
            "\r\n")


    def test_sendChunkedRequestBodyWithError(self):
        """
        If L{Request} is created with a C{bodyProducer} without a known length
        and the L{Deferred} returned from its C{startProducing} method fires
        with a L{Failure}, the L{Deferred} returned by L{Request.writeTo} fires
        with that L{Failure} and the body producer is unregistered from the
        transport.  The final zero-length chunk is not written to the
        transport.
        """
        producer = StringProducer(UNKNOWN_LENGTH)
        request = Request('POST', '/bar', _boringHeaders, producer)
        writeDeferred = request.writeTo(self.transport)
        self.transport.clear()
        producer.finished.errback(ArbitraryException())
        def cbFailed(ignored):
            self.assertEqual(self.transport.value(), "")
            self.assertIdentical(self.transport.producer, None)
        d = self.assertFailure(writeDeferred, ArbitraryException)
        d.addCallback(cbFailed)
        return d


    def test_sendRequestBodyWithLength(self):
        """
        If L{Request} is created with a C{bodyProducer} with a known length,
        that length is sent as the value for the I{Content-Length} header and
        chunked encoding is not used.
        """
        producer = StringProducer(3)
        request = Request('POST', '/bar', _boringHeaders, producer)
        request.writeTo(self.transport)

        self.assertNotIdentical(producer.consumer, None)
        self.assertIdentical(self.transport.producer, producer)
        self.assertTrue(self.transport.streaming)

        self.assertEqual(
            self.transport.value(),
            "POST /bar HTTP/1.1\r\n"
            "Connection: close\r\n"
            "Content-Length: 3\r\n"
            "Host: example.com\r\n"
            "\r\n")
        self.transport.clear()

        producer.consumer.write('abc')
        producer.finished.callback(None)
        self.assertIdentical(self.transport.producer, None)
        self.assertEqual(self.transport.value(), "abc")


    def test_sendRequestBodyWithTooFewBytes(self):
        """
        If L{Request} is created with a C{bodyProducer} with a known length and
        the producer does not produce that many bytes, the L{Deferred} returned
        by L{Request.writeTo} fires with a L{Failure} wrapping a
        L{WrongBodyLength} exception.
        """
        producer = StringProducer(3)
        request = Request('POST', '/bar', _boringHeaders, producer)
        writeDeferred = request.writeTo(self.transport)
        producer.consumer.write('ab')
        producer.finished.callback(None)
        self.assertIdentical(self.transport.producer, None)
        return self.assertFailure(writeDeferred, WrongBodyLength)


    def _sendRequestBodyWithTooManyBytesTest(self, finisher):
        """
        Verify that when too many bytes have been written by a body producer
        and then the body producer's C{startProducing} L{Deferred} fires that
        the producer is unregistered from the transport and that the
        L{Deferred} returned from L{Request.writeTo} is fired with a L{Failure}
        wrapping a L{WrongBodyLength}.

        @param finisher: A callable which will be invoked with the body
            producer after too many bytes have been written to the transport.
            It should fire the startProducing Deferred somehow.
        """
        producer = StringProducer(3)
        request = Request('POST', '/bar', _boringHeaders, producer)
        writeDeferred = request.writeTo(self.transport)

        producer.consumer.write('ab')

        # The producer hasn't misbehaved yet, so it shouldn't have been
        # stopped.
        self.assertFalse(producer.stopped)

        producer.consumer.write('cd')

        # Now the producer *has* misbehaved, so we should have tried to
        # make it stop.
        self.assertTrue(producer.stopped)

        # The transport should have had the producer unregistered from it as
        # well.
        self.assertIdentical(self.transport.producer, None)

        def cbFailed(exc):
            # The "cd" should not have been written to the transport because
            # the request can now locally be recognized to be invalid.  If we
            # had written the extra bytes, the server could have decided to
            # start processing the request, which would be bad since we're
            # going to indicate failure locally.
            self.assertEqual(
                self.transport.value(),
                "POST /bar HTTP/1.1\r\n"
                "Connection: close\r\n"
                "Content-Length: 3\r\n"
                "Host: example.com\r\n"
                "\r\n"
                "ab")
            self.transport.clear()

            # Subsequent writes should be ignored, as should firing the
            # Deferred returned from startProducing.
            self.assertRaises(ExcessWrite, producer.consumer.write, 'ef')

            # Likewise, if the Deferred returned from startProducing fires,
            # this should more or less be ignored (aside from possibly logging
            # an error).
            finisher(producer)

            # There should have been nothing further written to the transport.
            self.assertEqual(self.transport.value(), "")

        d = self.assertFailure(writeDeferred, WrongBodyLength)
        d.addCallback(cbFailed)
        return d


    def test_sendRequestBodyWithTooManyBytes(self):
        """
        If L{Request} is created with a C{bodyProducer} with a known length and
        the producer tries to produce more than than many bytes, the
        L{Deferred} returned by L{Request.writeTo} fires with a L{Failure}
        wrapping a L{WrongBodyLength} exception.
        """
        def finisher(producer):
            producer.finished.callback(None)
        return self._sendRequestBodyWithTooManyBytesTest(finisher)


    def test_sendRequestBodyErrorWithTooManyBytes(self):
        """
        If L{Request} is created with a C{bodyProducer} with a known length and
        the producer tries to produce more than than many bytes, the
        L{Deferred} returned by L{Request.writeTo} fires with a L{Failure}
        wrapping a L{WrongBodyLength} exception.
        """
        def finisher(producer):
            producer.finished.errback(ArbitraryException())
            errors = self.flushLoggedErrors(ArbitraryException)
            self.assertEqual(len(errors), 1)
        return self._sendRequestBodyWithTooManyBytesTest(finisher)


    def test_sendRequestBodyErrorWithConsumerError(self):
        """
        Though there should be no way for the internal C{finishedConsuming}
        L{Deferred} in L{Request._writeToContentLength} to fire a L{Failure}
        after the C{finishedProducing} L{Deferred} has fired, in case this does
        happen, the error should be logged with a message about how there's
        probably a bug in L{Request}.

        This is a whitebox test.
        """
        producer = StringProducer(3)
        request = Request('POST', '/bar', _boringHeaders, producer)
        request.writeTo(self.transport)

        finishedConsuming = producer.consumer._finished

        producer.consumer.write('abc')
        producer.finished.callback(None)

        finishedConsuming.errback(ArbitraryException())
        self.assertEqual(len(self.flushLoggedErrors(ArbitraryException)), 1)


    def _sendRequestBodyFinishedEarlyThenTooManyBytes(self, finisher):
        """
        Verify that if the body producer fires its Deferred and then keeps
        writing to the consumer that the extra writes are ignored and the
        L{Deferred} returned by L{Request.writeTo} fires with a L{Failure}
        wrapping the most appropriate exception type.
        """
        producer = StringProducer(3)
        request = Request('POST', '/bar', _boringHeaders, producer)
        writeDeferred = request.writeTo(self.transport)

        producer.consumer.write('ab')
        finisher(producer)
        self.assertIdentical(self.transport.producer, None)
        self.transport.clear()
        self.assertRaises(ExcessWrite, producer.consumer.write, 'cd')
        self.assertEqual(self.transport.value(), "")
        return writeDeferred


    def test_sendRequestBodyFinishedEarlyThenTooManyBytes(self):
        """
        If the request body producer indicates it is done by firing the
        L{Deferred} returned from its C{startProducing} method but then goes on
        to write too many bytes, the L{Deferred} returned by {Request.writeTo}
        fires with a L{Failure} wrapping L{WrongBodyLength}.
        """
        def finisher(producer):
            producer.finished.callback(None)
        return self.assertFailure(
            self._sendRequestBodyFinishedEarlyThenTooManyBytes(finisher),
            WrongBodyLength)


    def test_sendRequestBodyErroredEarlyThenTooManyBytes(self):
        """
        If the request body producer indicates an error by firing the
        L{Deferred} returned from its C{startProducing} method but then goes on
        to write too many bytes, the L{Deferred} returned by {Request.writeTo}
        fires with that L{Failure} and L{WrongBodyLength} is logged.
        """
        def finisher(producer):
            producer.finished.errback(ArbitraryException())
        return self.assertFailure(
            self._sendRequestBodyFinishedEarlyThenTooManyBytes(finisher),
            ArbitraryException)


    def test_sendChunkedRequestBodyFinishedThenWriteMore(self, _with=None):
        """
        If the request body producer with an unknown length tries to write
        after firing the L{Deferred} returned by its C{startProducing} method,
        the C{write} call raises an exception and does not write anything to
        the underlying transport.
        """
        producer = StringProducer(UNKNOWN_LENGTH)
        request = Request('POST', '/bar', _boringHeaders, producer)
        writeDeferred = request.writeTo(self.transport)
        producer.finished.callback(_with)
        self.transport.clear()

        self.assertRaises(ExcessWrite, producer.consumer.write, 'foo')
        self.assertEqual(self.transport.value(), "")
        return writeDeferred


    def test_sendChunkedRequestBodyFinishedWithErrorThenWriteMore(self):
        """
        If the request body producer with an unknown length tries to write
        after firing the L{Deferred} returned by its C{startProducing} method
        with a L{Failure}, the C{write} call raises an exception and does not
        write anything to the underlying transport.
        """
        d = self.test_sendChunkedRequestBodyFinishedThenWriteMore(
            Failure(ArbitraryException()))
        return self.assertFailure(d, ArbitraryException)


    def test_sendRequestBodyWithError(self):
        """
        If the L{Deferred} returned from the C{startProducing} method of the
        L{IBodyProducer} passed to L{Request} fires with a L{Failure}, the
        L{Deferred} returned from L{Request.writeTo} fails with that
        L{Failure}.
        """
        producer = StringProducer(5)
        request = Request('POST', '/bar', _boringHeaders, producer)
        writeDeferred = request.writeTo(self.transport)

        # Sanity check - the producer should be registered with the underlying
        # transport.
        self.assertIdentical(self.transport.producer, producer)
        self.assertTrue(self.transport.streaming)

        producer.consumer.write('ab')
        self.assertEqual(
            self.transport.value(),
            "POST /bar HTTP/1.1\r\n"
            "Connection: close\r\n"
            "Content-Length: 5\r\n"
            "Host: example.com\r\n"
            "\r\n"
            "ab")

        self.assertFalse(self.transport.disconnecting)
        producer.finished.errback(Failure(ArbitraryException()))

        # Disconnection is handled by a higher level.  Request should leave the
        # transport alone in this case.
        self.assertFalse(self.transport.disconnecting)

        # Oh.  Except it should unregister the producer that it registered.
        self.assertIdentical(self.transport.producer, None)

        return self.assertFailure(writeDeferred, ArbitraryException)


    def test_hostHeaderRequired(self):
        """
        L{Request.writeTo} raises L{BadHeaders} if there is not exactly one
        I{Host} header and writes nothing to the given transport.
        """
        request = Request('GET', '/', Headers({}), None)
        self.assertRaises(BadHeaders, request.writeTo, self.transport)
        self.assertEqual(self.transport.value(), '')

        request = Request('GET', '/', Headers({'Host': ['example.com', 'example.org']}), None)
        self.assertRaises(BadHeaders, request.writeTo, self.transport)
        self.assertEqual(self.transport.value(), '')


    def test_stopWriting(self):
        """
        L{Request.stopWriting} calls its body producer's C{stopProducing}
        method.
        """
        producer = StringProducer(3)
        request = Request('GET', '/', _boringHeaders, producer)
        request.writeTo(self.transport)
        self.assertFalse(producer.stopped)
        request.stopWriting()
        self.assertTrue(producer.stopped)


    def test_brokenStopProducing(self):
        """
        If the body producer's C{stopProducing} method raises an exception,
        L{Request.stopWriting} logs it and does not re-raise it.
        """
        producer = StringProducer(3)
        def brokenStopProducing():
            raise ArbitraryException("stopProducing is busted")
        producer.stopProducing = brokenStopProducing

        request = Request('GET', '/', _boringHeaders, producer)
        request.writeTo(self.transport)
        request.stopWriting()
        self.assertEqual(
            len(self.flushLoggedErrors(ArbitraryException)), 1)



class LengthEnforcingConsumerTests(TestCase):
    """
    Tests for L{LengthEnforcingConsumer}.
    """
    def setUp(self):
        self.result = Deferred()
        self.producer = StringProducer(10)
        self.transport = StringTransport()
        self.enforcer = LengthEnforcingConsumer(
            self.producer, self.transport, self.result)


    def test_write(self):
        """
        L{LengthEnforcingConsumer.write} calls the wrapped consumer's C{write}
        method with the bytes it is passed as long as there are fewer of them
        than the C{length} attribute indicates remain to be received.
        """
        self.enforcer.write('abc')
        self.assertEqual(self.transport.value(), 'abc')
        self.transport.clear()
        self.enforcer.write('def')
        self.assertEqual(self.transport.value(), 'def')


    def test_finishedEarly(self):
        """
        L{LengthEnforcingConsumer._noMoreWritesExpected} raises
        L{WrongBodyLength} if it is called before the indicated number of bytes
        have been written.
        """
        self.enforcer.write('x' * 9)
        self.assertRaises(WrongBodyLength, self.enforcer._noMoreWritesExpected)


    def test_writeTooMany(self, _unregisterAfter=False):
        """
        If it is called with a total number of bytes exceeding the indicated
        limit passed to L{LengthEnforcingConsumer.__init__},
        L{LengthEnforcingConsumer.write} fires the L{Deferred} with a
        L{Failure} wrapping a L{WrongBodyLength} and also calls the
        C{stopProducing} method of the producer.
        """
        self.enforcer.write('x' * 10)
        self.assertFalse(self.producer.stopped)
        self.enforcer.write('x')
        self.assertTrue(self.producer.stopped)
        if _unregisterAfter:
            self.enforcer._noMoreWritesExpected()
        return self.assertFailure(self.result, WrongBodyLength)


    def test_writeAfterNoMoreExpected(self):
        """
        If L{LengthEnforcingConsumer.write} is called after
        L{LengthEnforcingConsumer._noMoreWritesExpected}, it calls the
        producer's C{stopProducing} method and raises L{ExcessWrite}.
        """
        self.enforcer.write('x' * 10)
        self.enforcer._noMoreWritesExpected()
        self.assertFalse(self.producer.stopped)
        self.assertRaises(ExcessWrite, self.enforcer.write, 'x')
        self.assertTrue(self.producer.stopped)


    def test_finishedLate(self):
        """
        L{LengthEnforcingConsumer._noMoreWritesExpected} does nothing (in
        particular, it does not raise any exception) if called after too many
        bytes have been passed to C{write}.
        """
        return self.test_writeTooMany(True)


    def test_finished(self):
        """
        If L{LengthEnforcingConsumer._noMoreWritesExpected} is called after
        the correct number of bytes have been written it returns C{None}.
        """
        self.enforcer.write('x' * 10)
        self.assertIdentical(self.enforcer._noMoreWritesExpected(), None)


    def test_stopProducingRaises(self):
        """
        If L{LengthEnforcingConsumer.write} calls the producer's
        C{stopProducing} because too many bytes were written and the
        C{stopProducing} method raises an exception, the exception is logged
        and the L{LengthEnforcingConsumer} still errbacks the finished
        L{Deferred}.
        """
        def brokenStopProducing():
            StringProducer.stopProducing(self.producer)
            raise ArbitraryException("stopProducing is busted")
        self.producer.stopProducing = brokenStopProducing

        def cbFinished(ignored):
            self.assertEqual(
                len(self.flushLoggedErrors(ArbitraryException)), 1)
        d = self.test_writeTooMany()
        d.addCallback(cbFinished)
        return d



class RequestBodyConsumerTests(TestCase):
    """
    Tests for L{ChunkedEncoder} which sits between an L{ITransport} and a
    request/response body producer and chunked encodes everything written to
    it.
    """
    def test_interface(self):
        """
        L{ChunkedEncoder} instances provide L{IConsumer}.
        """
        self.assertTrue(
            verifyObject(IConsumer, ChunkedEncoder(StringTransport())))


    def test_write(self):
        """
        L{ChunkedEncoder.write} writes to the transport the chunked encoded
        form of the bytes passed to it.
        """
        transport = StringTransport()
        encoder = ChunkedEncoder(transport)
        encoder.write('foo')
        self.assertEqual(transport.value(), '3\r\nfoo\r\n')
        transport.clear()
        encoder.write('x' * 16)
        self.assertEqual(transport.value(), '10\r\n' + 'x' * 16 + '\r\n')


    def test_producerRegistration(self):
        """
        L{ChunkedEncoder.registerProducer} registers the given streaming
        producer with its transport and L{ChunkedEncoder.unregisterProducer}
        writes a zero-length chunk to its transport and unregisters the
        transport's producer.
        """
        transport = StringTransport()
        producer = object()
        encoder = ChunkedEncoder(transport)
        encoder.registerProducer(producer, True)
        self.assertIdentical(transport.producer, producer)
        self.assertTrue(transport.streaming)
        encoder.unregisterProducer()
        self.assertIdentical(transport.producer, None)
        self.assertEqual(transport.value(), '0\r\n\r\n')



class TransportProxyProducerTests(TestCase):
    """
    Tests for L{TransportProxyProducer} which proxies the L{IPushProducer}
    interface of a transport.
    """
    def test_interface(self):
        """
        L{TransportProxyProducer} instances provide L{IPushProducer}.
        """
        self.assertTrue(
            verifyObject(IPushProducer, TransportProxyProducer(None)))


    def test_stopProxyingUnreferencesProducer(self):
        """
        L{TransportProxyProducer._stopProxying} drops the reference to the
        wrapped L{IPushProducer} provider.
        """
        transport = StringTransport()
        proxy = TransportProxyProducer(transport)
        self.assertIdentical(proxy._producer, transport)
        proxy._stopProxying()
        self.assertIdentical(proxy._producer, None)


    def test_resumeProducing(self):
        """
        L{TransportProxyProducer.resumeProducing} calls the wrapped
        transport's C{resumeProducing} method unless told to stop proxying.
        """
        transport = StringTransport()
        transport.pauseProducing()

        proxy = TransportProxyProducer(transport)
        # The transport should still be paused.
        self.assertEqual(transport.producerState, 'paused')
        proxy.resumeProducing()
        # The transport should now be resumed.
        self.assertEqual(transport.producerState, 'producing')

        transport.pauseProducing()
        proxy._stopProxying()

        # The proxy should no longer do anything to the transport.
        proxy.resumeProducing()
        self.assertEqual(transport.producerState, 'paused')


    def test_pauseProducing(self):
        """
        L{TransportProxyProducer.pauseProducing} calls the wrapped transport's
        C{pauseProducing} method unless told to stop proxying.
        """
        transport = StringTransport()

        proxy = TransportProxyProducer(transport)
        # The transport should still be producing.
        self.assertEqual(transport.producerState, 'producing')
        proxy.pauseProducing()
        # The transport should now be paused.
        self.assertEqual(transport.producerState, 'paused')

        transport.resumeProducing()
        proxy._stopProxying()

        # The proxy should no longer do anything to the transport.
        proxy.pauseProducing()
        self.assertEqual(transport.producerState, 'producing')


    def test_stopProducing(self):
        """
        L{TransportProxyProducer.stopProducing} calls the wrapped transport's
        C{stopProducing} method unless told to stop proxying.
        """
        transport = StringTransport()
        proxy = TransportProxyProducer(transport)
        # The transport should still be producing.
        self.assertEqual(transport.producerState, 'producing')
        proxy.stopProducing()
        # The transport should now be stopped.
        self.assertEqual(transport.producerState, 'stopped')

        transport = StringTransport()
        proxy = TransportProxyProducer(transport)
        proxy._stopProxying()
        proxy.stopProducing()
        # The transport should not have been stopped.
        self.assertEqual(transport.producerState, 'producing')



class ResponseTests(TestCase):
    """
    Tests for L{Response}.
    """

    def test_verifyInterface(self):
        """
        L{Response} instances provide L{IResponse}.
        """
        response = justTransportResponse(StringTransport())
        self.assertTrue(verifyObject(IResponse, response))


    def test_makeConnection(self):
        """
        The L{IProtocol} provider passed to L{Response.deliverBody} has its
        C{makeConnection} method called with an L{IPushProducer} provider
        hooked up to the response as an argument.
        """
        producers = []
        transport = StringTransport()
        class SomeProtocol(Protocol):
            def makeConnection(self, producer):
                producers.append(producer)

        consumer = SomeProtocol()
        response = justTransportResponse(transport)
        response.deliverBody(consumer)
        [theProducer] = producers
        theProducer.pauseProducing()
        self.assertEqual(transport.producerState, 'paused')
        theProducer.resumeProducing()
        self.assertEqual(transport.producerState, 'producing')


    def test_dataReceived(self):
        """
        The L{IProtocol} provider passed to L{Response.deliverBody} has its
        C{dataReceived} method called with bytes received as part of the
        response body.
        """
        bytes = []
        class ListConsumer(Protocol):
            def dataReceived(self, data):
                bytes.append(data)


        consumer = ListConsumer()
        response = justTransportResponse(StringTransport())
        response.deliverBody(consumer)

        response._bodyDataReceived('foo')
        self.assertEqual(bytes, ['foo'])


    def test_connectionLost(self):
        """
        The L{IProtocol} provider passed to L{Response.deliverBody} has its
        C{connectionLost} method called with a L{Failure} wrapping
        L{ResponseDone} when the response's C{_bodyDataFinished} method is
        called.
        """
        lost = []
        class ListConsumer(Protocol):
            def connectionLost(self, reason):
                lost.append(reason)

        consumer = ListConsumer()
        response = justTransportResponse(StringTransport())
        response.deliverBody(consumer)

        response._bodyDataFinished()
        lost[0].trap(ResponseDone)
        self.assertEqual(len(lost), 1)

        # The protocol reference should be dropped, too, to facilitate GC or
        # whatever.
        self.assertIdentical(response._bodyProtocol, None)


    def test_bufferEarlyData(self):
        """
        If data is delivered to the L{Response} before a protocol is registered
        with C{deliverBody}, that data is buffered until the protocol is
        registered and then is delivered.
        """
        bytes = []
        class ListConsumer(Protocol):
            def dataReceived(self, data):
                bytes.append(data)

        protocol = ListConsumer()
        response = justTransportResponse(StringTransport())
        response._bodyDataReceived('foo')
        response._bodyDataReceived('bar')
        response.deliverBody(protocol)
        response._bodyDataReceived('baz')
        self.assertEqual(bytes, ['foo', 'bar', 'baz'])
        # Make sure the implementation-detail-byte-buffer is cleared because
        # not clearing it wastes memory.
        self.assertIdentical(response._bodyBuffer, None)


    def test_multipleStartProducingFails(self):
        """
        L{Response.deliverBody} raises L{RuntimeError} if called more than
        once.
        """
        response = justTransportResponse(StringTransport())
        response.deliverBody(Protocol())
        self.assertRaises(RuntimeError, response.deliverBody, Protocol())


    def test_startProducingAfterFinishedFails(self):
        """
        L{Response.deliverBody} raises L{RuntimeError} if called after
        L{Response._bodyDataFinished}.
        """
        response = justTransportResponse(StringTransport())
        response.deliverBody(Protocol())
        response._bodyDataFinished()
        self.assertRaises(RuntimeError, response.deliverBody, Protocol())


    def test_bodyDataReceivedAfterFinishedFails(self):
        """
        L{Response._bodyDataReceived} raises L{RuntimeError} if called after
        L{Response._bodyDataFinished} but before L{Response.deliverBody}.
        """
        response = justTransportResponse(StringTransport())
        response._bodyDataFinished()
        self.assertRaises(RuntimeError, response._bodyDataReceived, 'foo')


    def test_bodyDataReceivedAfterDeliveryFails(self):
        """
        L{Response._bodyDataReceived} raises L{RuntimeError} if called after
        L{Response._bodyDataFinished} and after L{Response.deliverBody}.
        """
        response = justTransportResponse(StringTransport())
        response._bodyDataFinished()
        response.deliverBody(Protocol())
        self.assertRaises(RuntimeError, response._bodyDataReceived, 'foo')


    def test_bodyDataFinishedAfterFinishedFails(self):
        """
        L{Response._bodyDataFinished} raises L{RuntimeError} if called more
        than once.
        """
        response = justTransportResponse(StringTransport())
        response._bodyDataFinished()
        self.assertRaises(RuntimeError, response._bodyDataFinished)


    def test_bodyDataFinishedAfterDeliveryFails(self):
        """
        L{Response._bodyDataFinished} raises L{RuntimeError} if called after
        the body has been delivered.
        """
        response = justTransportResponse(StringTransport())
        response._bodyDataFinished()
        response.deliverBody(Protocol())
        self.assertRaises(RuntimeError, response._bodyDataFinished)


    def test_transportResumed(self):
        """
        L{Response.deliverBody} resumes the HTTP connection's transport
        before passing it to the transport's C{makeConnection} method.
        """
        transportState = []
        class ListConsumer(Protocol):
            def makeConnection(self, transport):
                transportState.append(transport.producerState)

        transport = StringTransport()
        transport.pauseProducing()
        protocol = ListConsumer()
        response = justTransportResponse(transport)
        self.assertEqual(transport.producerState, 'paused')
        response.deliverBody(protocol)
        self.assertEqual(transportState, ['producing'])


    def test_bodyDataFinishedBeforeStartProducing(self):
        """
        If the entire body is delivered to the L{Response} before the
        response's C{deliverBody} method is called, the protocol passed to
        C{deliverBody} is immediately given the body data and then
        disconnected.
        """
        transport = StringTransport()
        response = justTransportResponse(transport)
        response._bodyDataReceived('foo')
        response._bodyDataReceived('bar')
        response._bodyDataFinished()

        protocol = AccumulatingProtocol()
        response.deliverBody(protocol)
        self.assertEqual(protocol.data, 'foobar')
        protocol.closedReason.trap(ResponseDone)


    def test_finishedWithErrorWhenConnected(self):
        """
        The L{Failure} passed to L{Response._bodyDataFinished} when the response
        is in the I{connected} state is passed to the C{connectionLost} method
        of the L{IProtocol} provider passed to the L{Response}'s
        C{deliverBody} method.
        """
        transport = StringTransport()
        response = justTransportResponse(transport)

        protocol = AccumulatingProtocol()
        response.deliverBody(protocol)

        # Sanity check - this test is for the connected state
        self.assertEqual(response._state, 'CONNECTED')
        response._bodyDataFinished(Failure(ArbitraryException()))

        protocol.closedReason.trap(ArbitraryException)


    def test_finishedWithErrorWhenInitial(self):
        """
        The L{Failure} passed to L{Response._bodyDataFinished} when the response
        is in the I{initial} state is passed to the C{connectionLost} method of
        the L{IProtocol} provider passed to the L{Response}'s C{deliverBody}
        method.
        """
        transport = StringTransport()
        response = justTransportResponse(transport)

        # Sanity check - this test is for the initial state
        self.assertEqual(response._state, 'INITIAL')
        response._bodyDataFinished(Failure(ArbitraryException()))

        protocol = AccumulatingProtocol()
        response.deliverBody(protocol)

        protocol.closedReason.trap(ArbitraryException)
