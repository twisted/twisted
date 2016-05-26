# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test HTTP/2 support.
"""

from __future__ import absolute_import, division

import itertools
import json

from twisted.internet import defer
from twisted.protocols.test.test_tls import NonStreamingProducer
from twisted.python.compat import iterbytes
from twisted.test.proto_helpers import StringTransport
from twisted.test.test_internet import DummyProducer
from twisted.trial import unittest
from twisted.web import http
from twisted.web.test.test_http import DummyHTTPHandler

skipH2 = None

try:
    from twisted.web.http2 import H2Connection

    # These third-party imports are guaranteed to be present if HTTP/2 support
    # is compiled in. We do not use them in the main code: only in the tests.
    import h2
    import hyperframe
    from hpack.hpack import Encoder, Decoder
except ImportError:
    skipH2 = "HTTP/2 support not enabled"



# Define some helpers for the rest of these tests.
class FrameFactory(object):
    """
    A class containing lots of helper methods and state to build frames. This
    allows test cases to easily build correct HTTP/2 frames to feed to
    hyper-h2.
    """
    def __init__(self):
        self.encoder = Encoder()


    def refreshEncoder(self):
        self.encoder = Encoder()


    def preamble(self):
        return b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'


    def buildHeadersFrame(self,
                          headers,
                          flags=[],
                          streamID=1,
                          **priorityKwargs):
        """
        Builds a single valid headers frame out of the contained headers.
        """
        f = hyperframe.frame.HeadersFrame(streamID)
        f.data = self.encoder.encode(headers)
        f.flags.add('END_HEADERS')
        for flag in flags:
            f.flags.add(flag)

        for k, v in priorityKwargs.items():
            setattr(f, k, v)

        return f


    def buildDataFrame(self, data, flags=None, streamID=1):
        """
        Builds a single data frame out of a chunk of data.
        """
        flags = set(flags) if flags is not None else set()
        f = hyperframe.frame.DataFrame(streamID)
        f.data = data
        f.flags = flags
        return f


    def buildSettingsFrame(self, settings, ack=False):
        """
        Builds a single settings frame.
        """
        f = hyperframe.frame.SettingsFrame(0)
        if ack:
            f.flags.add('ACK')

        f.settings = settings
        return f


    def buildWindowUpdateFrame(self, streamID, increment):
        """
        Builds a single WindowUpdate frame.
        """
        f = hyperframe.frame.WindowUpdateFrame(streamID)
        f.window_increment = increment
        return f


    def buildGoAwayFrame(self, lastStreamID, errorCode=0, additionalData=b''):
        """
        Builds a single GOAWAY frame.
        """
        f = hyperframe.frame.GoAwayFrame(0)
        f.error_code = errorCode
        f.last_stream_id = lastStreamID
        f.additional_data = additionalData
        return f


    def buildRstStreamFrame(self, streamID, errorCode=0):
        """
        Builds a single RST_STREAM frame.
        """
        f = hyperframe.frame.RstStreamFrame(streamID)
        f.error_code = errorCode
        return f


    def buildPriorityFrame(self,
                           streamID,
                           weight,
                           dependsOn=0,
                           exclusive=False):
        """
        Builds a single priority frame.
        """
        f = hyperframe.frame.PriorityFrame(streamID)
        f.depends_on = dependsOn
        f.stream_weight = weight
        f.exclusive = exclusive
        return f


    def buildPushPromiseFrame(self,
                              streamID,
                              promisedStreamID,
                              headers,
                              flags=[]):
        """
        Builds a single Push Promise frame.
        """
        f = hyperframe.frame.PushPromiseFrame(streamID)
        f.promised_stream_id = promisedStreamID
        f.data = self.encoder.encode(headers)
        f.flags = set(flags)
        f.flags.add('END_HEADERS')
        return f



class FrameBuffer(object):
    """
    A test object that converts data received from Twisted's HTTP/2 stack and
    turns it into a sequence of hyperframe frame objects.

    This is primarily used to make it easier to write and debug tests: rather
    than have to serialize the expected frames and then do byte-level
    comparison (which can be unclear in debugging output), this object makes it
    possible to work with the frames directly.

    It also ensures that headers are properly decompressed.
    """
    def __init__(self):
        self.decoder = Decoder()
        self._data = b''


    def receiveData(self, data):
        self._data += data


    def __iter__(self):
        return self


    def next(self):
        if len(self._data) < 9:
            raise StopIteration()

        frame, length = hyperframe.frame.Frame.parse_frame_header(
            self._data[:9]
        )
        if len(self._data) < length + 9:
            raise StopIteration()

        frame.parse_body(memoryview(self._data[9:9+length]))
        self._data = self._data[9+length:]

        if isinstance(frame, hyperframe.frame.HeadersFrame):
            frame.data = self.decoder.decode(frame.data)

        return frame


    __next__ = next



def buildRequestFrames(headers, data, frameFactory=None, streamID=1):
    """
    Provides a sequence of HTTP/2 frames that encode a single HTTP request.
    This should be used when you want to control the serialization yourself,
    e.g. because you want to interleave other frames with these. If that's not
    necessary, prefer L{buildRequestBytes}.

    @param headers: The HTTP/2 headers to send.
    @type headers: L{list} of L{tuple} of L{bytes}

    @param data: The HTTP data to send. Each list entry will be sent in its own
    frame.
    @type data: L{list} of L{bytes}

    @param frameFactory: The L{FrameFactory} that will be used to construct the
    frames.
    @type frameFactory: L{FrameFactory}

    @param streamID: The ID of the stream on which to send the request.
    @type streamID: L{int}
    """
    if frameFactory is None:
        frameFactory = FrameFactory()

    frames = []
    frames.append(
        frameFactory.buildHeadersFrame(headers=headers, streamID=streamID)
    )
    frames.extend(
        frameFactory.buildDataFrame(chunk, streamID=streamID) for chunk in data
    )
    frames[-1].flags.add('END_STREAM')
    return frames



def buildRequestBytes(headers, data, frameFactory=None, streamID=1):
    """
    Provides the byte sequence for a collection of HTTP/2 frames representing
    the provided request.

    @param headers: The HTTP/2 headers to send.
    @type headers: L{list} of L{tuple} of L{bytes}

    @param data: The HTTP data to send. Each list entry will be sent in its own
    frame.
    @type data: L{list} of L{bytes}

    @param frameFactory: The L{FrameFactory} that will be used to construct the
    frames.
    @type frameFactory: L{FrameFactory}

    @param streamID: The ID of the stream on which to send the request.
    @type streamID: L{int}
    """
    frames = buildRequestFrames(headers, data, frameFactory, streamID)
    return b''.join(f.serialize() for f in frames)



class ChunkedHTTPHandler(http.Request):
    """
    A HTTP request object that writes chunks of data back to the network based
    on the URL.

    Must be called with a path /chunked/<num_chunks>
    """
    chunkData = b'hello world!'

    def process(self):
        chunks = int(self.uri.split(b'/')[-1])
        self.setResponseCode(200)

        for _ in range(chunks):
            self.write(self.chunkData)

        self.finish()



class ConsumerDummyHandler(http.Request):
    """
    This is a HTTP request handler that works with the C{IPushProducer}
    implementation in the L{H2Stream} object. No current IRequest object does
    that, but in principle future implementations could: that codepath should
    therefore be tested.
    """
    def __init__(self, *args, **kwargs):
        http.Request.__init__(self, *args, **kwargs)

        # Production starts paused.
        self.channel.pauseProducing()
        self._requestReceived = False
        self._data = None


    def acceptData(self):
        """
        Start the data pipe.
        """
        self.channel.resumeProducing()


    def requestReceived(self, *args, **kwargs):
        self._requestReceived = True
        return http.Request.requestReceived(self, *args, **kwargs)


    def process(self):
        self.setResponseCode(200)
        self._data = self.content.read()
        returnData = b'this is a response from a consumer dummy handler'
        self.write(returnData)
        self.finish()



class AbortingConsumerDummyHandler(ConsumerDummyHandler):
    """
    This is a HTTP request handler that works with the C{IPushProducer}
    implementation in the L{H2Stream} object. The difference between this and
    the ConsumerDummyHandler is that after resuming production it immediately
    aborts it again.
    """
    def acceptData(self):
        """
        Start and then immediately stop the data pipe.
        """
        self.channel.resumeProducing()
        self.channel.stopProducing()



class DummyProducerHandler(http.Request):
    """
    An HTTP request handler that registers a dummy producer to serve the body.

    The owner must call C{finish} to complete the response.
    """
    def process(self):
        self.setResponseCode(200)
        self.registerProducer(DummyProducer(), True)



class DummyPullProducerHandler(http.Request):
    """
    An HTTP request handler that registers a dummy pull producer to serve the
    body.

    The owner must call C{finish} to complete the response.
    """
    def process(self):
        self._actualProducer = NonStreamingProducer(self)
        self.setResponseCode(200)
        self.registerProducer(self._actualProducer, False)



class HTTP2ServerTests(unittest.TestCase):
    if skipH2:
        skip = skipH2


    getRequestHeaders = [
        (':method', 'GET'),
        (':authority', 'localhost'),
        (':path', '/'),
        (':scheme', 'https'),
        ('user-agent', 'twisted-test-code'),
        ('custom-header', '1'),
        ('custom-header', '2'),
    ]


    postRequestHeaders = [
        (':method', 'POST'),
        (':authority', 'localhost'),
        (':path', '/post_endpoint'),
        (':scheme', 'https'),
        ('user-agent', 'twisted-test-code'),
        ('content-length', '25'),
    ]


    postRequestData = [b"hello ", b"world, ", b"it's ", b"http/2!"]


    getResponseHeaders = [
        (':status', '200'),
        ('request', '/'),
        ('command', 'GET'),
        ('version', 'HTTP/2'),
        ('content-length', '13'),
    ]


    getResponseData = b"'''\nNone\n'''\n"


    postResponseHeaders = [
        (':status', '200'),
        ('request', '/post_endpoint'),
        ('command', 'POST'),
        ('version', 'HTTP/2'),
        ('content-length', '36'),
    ]


    postResponseData = b"'''\n25\nhello world, it's http/2!'''\n"


    def test_basicRequest(self):
        """
        Send request over a TCP connection and confirm that we get back the
        expected data in the order and style we expect.
        """
        # This test is complex because it validates the data very closely: it
        # specifically checks frame ordering and type.
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyHTTPHandler

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(self.getRequestHeaders, [], f)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            self.assertEqual(len(frames), 4)
            self.assertTrue(all(f.stream_id == 1 for f in frames[1:]))

            self.assertTrue(
                isinstance(frames[1], hyperframe.frame.HeadersFrame)
            )
            self.assertTrue(isinstance(frames[2], hyperframe.frame.DataFrame))
            self.assertTrue(isinstance(frames[3], hyperframe.frame.DataFrame))

            self.assertEqual(
                dict(frames[1].data), dict(self.getResponseHeaders)
            )
            self.assertEqual(frames[2].data, self.getResponseData)
            self.assertEqual(frames[3].data, b'')
            self.assertTrue('END_STREAM' in frames[3].flags)

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_postRequest(self):
        """
        Send a POST request and confirm that the data is safely transferred.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyHTTPHandler

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(
            self.postRequestHeaders, self.postRequestData, f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # One Settings frame, 8 WindowUpdate frames, one Headers frame,
            # and two Data frames
            self.assertEqual(len(frames), 12)
            self.assertTrue(all(f.stream_id == 1 for f in frames[-3:]))

            self.assertTrue(
                isinstance(frames[-3], hyperframe.frame.HeadersFrame)
            )
            self.assertTrue(isinstance(frames[-2], hyperframe.frame.DataFrame))
            self.assertTrue(isinstance(frames[-1], hyperframe.frame.DataFrame))

            self.assertEqual(
                dict(frames[-3].data), dict(self.postResponseHeaders)
            )
            self.assertEqual(frames[-2].data, self.postResponseData)
            self.assertEqual(frames[-1].data, b'')
            self.assertTrue('END_STREAM' in frames[-1].flags)

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_interleavedRequests(self):
        """
        Many interleaved POST requests all get received and responded to
        appropriately.
        """
        # Unfortunately this test is pretty complex.
        REQUEST_COUNT = 40

        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyHTTPHandler

        # Stream IDs are always odd numbers.
        streamIDs = list(range(1, REQUEST_COUNT * 2, 2))
        frames = [
            buildRequestFrames(
                self.postRequestHeaders, self.postRequestData, f, streamID
            ) for streamID in streamIDs
        ]

        requestBytes = f.preamble()

        # Interleave the frames. That is, send one frame from each stream at a
        # time. This wacky line lets us do that.
        frames = itertools.chain.from_iterable(zip(*frames))
        requestBytes += b''.join(frame.serialize() for frame in frames)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        def validate(results):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # We expect 1 Settings frame for the connection, and then 11 frames
            # *per stream* (8 WindowUpdate frames, 1 Headers frame,
            # 2 Data frames).
            self.assertEqual(len(frames), 1 + (11 * 40))

            # Let's check the data is ok. We need the non-WindowUpdate frames
            # for each stream.
            for streamID in streamIDs:
                streamFrames = [
                    f for f in frames if f.stream_id == streamID and
                    not isinstance(f, hyperframe.frame.WindowUpdateFrame)
                ]

                self.assertEqual(len(streamFrames), 3)

                self.assertEqual(
                    dict(streamFrames[0].data), dict(self.postResponseHeaders)
                )
                self.assertEqual(streamFrames[1].data, self.postResponseData)
                self.assertEqual(streamFrames[2].data, b'')
                self.assertTrue('END_STREAM' in streamFrames[2].flags)

        return defer.DeferredList(
            list(a._streamCleanupCallbacks.values())
        ).addCallback(validate)


    def test_sendAccordingToPriority(self):
        """
        Data in responses is interleaved according to HTTP/2 priorities.
        """
        # We want to start three parallel GET requests that will each return
        # four chunks of data. These chunks will be interleaved according to
        # HTTP/2 priorities. Stream 1 will be set to weight 64, Stream 3 to
        # weight 32, and Stream 5 to weight 16 but dependent on Stream 1.
        # That will cause data frames for these streams to be emitted in this
        # order: 1, 1, 3, 1, 1, 3, 1, 5, 3, 3, 5, 3, 5, 5, 5.
        #
        # The reason there are so many frames is because the implementation
        # interleaves stream completion according to priority order as well,
        # because it is sent on a Data frame.
        #
        # This doesn't fully test priority, but tests *almost* enough of it to
        # be worthwhile.
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = ChunkedHTTPHandler
        getRequestHeaders = self.getRequestHeaders
        getRequestHeaders[2] = (':path', '/chunked/4')

        frames = [
            buildRequestFrames(getRequestHeaders, [], f, streamID)
            for streamID in [1, 3, 5]
        ]

        # Set the priorities. The first two will use their HEADERS frame, the
        # third will have a PRIORITY frame sent before the headers.
        frames[0][0].flags.add('PRIORITY')
        frames[0][0].stream_weight = 64

        frames[1][0].flags.add('PRIORITY')
        frames[1][0].stream_weight = 32

        priorityFrame = f.buildPriorityFrame(
            streamID=5,
            weight=16,
            dependsOn=1,
            exclusive=True,
        )
        frames[2].insert(0, priorityFrame)

        frames = itertools.chain.from_iterable(frames)
        requestBytes = f.preamble()
        requestBytes += b''.join(frame.serialize() for frame in frames)

        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        def validate(results):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # We expect 1 Settings frame for the connection, and then 6 frames
            # per stream (1 Headers frame, 5 data frames), for a total of 19.
            self.assertEqual(len(frames), 19)

            streamIDs = [
                f.stream_id for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            expectedOrder = [1, 1, 3, 1, 1, 3, 1, 5, 3, 3, 5, 3, 5, 5, 5]
            self.assertEqual(streamIDs, expectedOrder)

        return defer.DeferredList(
            list(a._streamCleanupCallbacks.values())
        ).addCallback(validate)


    def test_protocolErrorTerminatesConnection(self):
        """
        A protocol error from the remote peer terminates the connection.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyHTTPHandler

        # We're going to open a stream and then send a PUSH_PROMISE frame,
        # which is forbidden.
        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(self.getRequestHeaders, [], f)
        requestBytes += f.buildPushPromiseFrame(
            streamID=1,
            promisedStreamID=2,
            headers=self.getRequestHeaders,
            flags=['END_HEADERS'],
        ).serialize()

        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

            # Check whether the transport got shut down: if it did, stop
            # sending more data.
            if b.disconnecting:
                break

        buffer = FrameBuffer()
        buffer.receiveData(b.value())
        frames = list(buffer)

        # The send loop never gets to terminate the stream, but *some* data
        # does get sent. We get a Settings frame, a Headers frame, a Data
        # frame, and then the GoAway frame.
        self.assertEqual(len(frames), 4)
        self.assertTrue(
            isinstance(frames[3], hyperframe.frame.GoAwayFrame)
        )
        self.assertTrue(b.disconnecting)
        self.assertFalse(a._sender.running)


    def test_streamProducingData(self):
        """
        The H2Stream data implements IPushProducer, and can have its data
        production controlled by the Request if the Request chooses to.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = ConsumerDummyHandler

        # We're going to send in a POST request.
        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(
            self.postRequestHeaders, self.postRequestData, f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # At this point no data should have been received by the request *or*
        # the response. We need to dig the request out of the tree of objects.
        request = a.streams[1]._request
        self.assertFalse(request._requestReceived)

        # We should have only received the Settings frame. It's important that
        # the WindowUpdate frames don't land before data is delivered to the
        # Request.
        buffer = FrameBuffer()
        buffer.receiveData(b.value())
        frames = list(buffer)
        self.assertEqual(len(frames), 1)

        # At this point, we can kick off the producing. This will force the
        # H2Stream object to deliver the request data all at once, so check
        # that it was delivered correctly.
        request.acceptData()
        self.assertTrue(request._requestReceived)
        self.assertTrue(request._data, b"hello world, it's http/2!")

        # *That* will have also caused the H2Connection object to emit almost
        # all the data it needs. That'll be a Headers frame and the first Data
        # frame, as well as two WindowUpdate frames.
        buffer = FrameBuffer()
        buffer.receiveData(b.value())
        frames = list(buffer)
        self.assertEqual(len(frames), 5)

        def validate(streamID):
            # Confirm that the response is ok.
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # The only new frame here is one more Data frame that carries the
            # END_STREAM sentinel.
            self.assertEqual(len(frames), 6)
            self.assertTrue('END_STREAM' in frames[-1].flags)

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_abortStreamProducingData(self):
        """
        The H2Stream data implements IPushProducer, and can have its data
        production controlled by the Request if the Request chooses to.
        When the production is stopped, that causes the stream connection to
        be lost.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = AbortingConsumerDummyHandler

        # We're going to send in a POST request.
        frames = buildRequestFrames(
            self.postRequestHeaders, self.postRequestData, f
        )
        frames[-1].flags = set()  # Remove END_STREAM flag.
        requestBytes = f.preamble()
        requestBytes += b''.join(f.serialize() for f in frames)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # At this point no data should have been received by the request *or*
        # the response. We need to dig the request out of the tree of objects.
        request = a.streams[1]._request
        self.assertFalse(request._requestReceived)

        # Save off the cleanup deferred now, it'll be removed when the
        # RstStream frame is sent.
        cleanupCallback = a._streamCleanupCallbacks[1]

        # At this point, we can kick off the production and immediate abort.
        request.acceptData()

        # The stream will now have been aborted.
        def validate(streamID):
            # Confirm that the response is ok.
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # We expect a Settings frame, two WindowUpdate frames, and a
            # RstStream frame.
            self.assertEqual(len(frames), 4)
            self.assertTrue(
                isinstance(frames[3], hyperframe.frame.RstStreamFrame)
            )
            self.assertEqual(frames[3].stream_id, 1)

        return cleanupCallback.addCallback(validate)


    def test_terminatedRequest(self):
        """
        When a RstStream frame is received, the L{H2Connection} and L{H2Stream}
        objects tear down the L{http.Request} and swallow all outstanding
        writes.
        """
        # Here we want to use the DummyProducerHandler primarily for the side
        # effect it has of not writing to the connection. That means we can
        # delay some writes until *after* the RstStream frame is received.
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(self.getRequestHeaders, [], f)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Get the request object.
        request = a.streams[1]._request

        # Send two writes in.
        request.write(b"first chunk")
        request.write(b"second chunk")

        # Save off the cleanup deferred now, it'll be removed when the
        # RstStream frame is received.
        cleanupCallback = a._streamCleanupCallbacks[1]

        # Now fire the RstStream frame.
        a.dataReceived(
            f.buildRstStreamFrame(1, errorCode=1).serialize()
        )

        # This should have cancelled the request.
        self.assertTrue(request._disconnected)
        self.assertTrue(request.channel is None)

        # An attempt to write should at this point raise an exception.
        self.assertRaises(AttributeError, request.write, b"third chunk")

        # Check that everything is fine.
        # We expect that only the Settings, Headers, and one Data frame will
        # have been emitted. The first Data frame will be the original write,
        # which got executed *before* the RstStream frame was received. The
        # second write is lost because the looping call never had another
        # chance to execute before the RstStream frame got processed.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            self.assertEqual(len(frames), 3)
            self.assertTrue(all(f.stream_id == 1 for f in frames[1:]))

            self.assertTrue(
                isinstance(frames[1], hyperframe.frame.HeadersFrame)
            )

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(dataChunks, [b"first chunk"])

        return cleanupCallback.addCallback(validate)


    def test_terminatedConnection(self):
        """
        When a GoAway frame is received, the L{H2Connection} and L{H2Stream}
        objects tear down all outstanding L{http.Request} objects and stop all
        writing.
        """
        # Here we want to use the DummyProducerHandler primarily for the side
        # effect it has of not writing to the connection. That means we can
        # delay some writes until *after* the GoAway frame is received.
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(self.getRequestHeaders, [], f)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Get the request object.
        request = a.streams[1]._request

        # Send two writes in.
        request.write(b"first chunk")
        request.write(b"second chunk")

        # Save off the cleanup deferred now, it'll be removed when the
        # GoAway frame is received.
        cleanupCallback = a._streamCleanupCallbacks[1]

        # Now fire the GoAway frame.
        a.dataReceived(
            f.buildGoAwayFrame(lastStreamID=0).serialize()
        )

        # This should have cancelled the request.
        self.assertTrue(request._disconnected)
        self.assertTrue(request.channel is None)

        # It should also have cancelled the sending loop.
        self.assertFalse(a._sender.running)

        # Check that everything is fine.
        # We expect that only the Settings, Headers, and one Data frame will
        # have been emitted. The first Data frame will be the original write,
        # which got executed *before* the GoAway frame was received. The
        # second write is lost because the looping call never had another
        # chance to execute before the GoAway frame got processed.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            self.assertEqual(len(frames), 3)
            self.assertTrue(all(f.stream_id == 1 for f in frames[1:]))

            self.assertTrue(
                isinstance(frames[1], hyperframe.frame.HeadersFrame)
            )

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(dataChunks, [b"first chunk"])

        return cleanupCallback.addCallback(validate)


    def test_respondWith100Continue(self):
        """
        Requests containing Expect: 100-continue cause provisional 100
        responses to be emitted.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyHTTPHandler

        # Add Expect: 100-continue for this request.
        headers = self.getRequestHeaders + [('expect', '100-continue')]

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(headers, [], f)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # We expect 5 frames now: Settings, two Headers frames, and two Data
        # frames. We're only really interested in validating the first Headers
        # frame which contains the 100.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            self.assertEqual(len(frames), 5)
            self.assertTrue(all(f.stream_id == 1 for f in frames[1:]))

            self.assertTrue(
                isinstance(frames[1], hyperframe.frame.HeadersFrame)
            )
            self.assertEqual(
                frames[1].data, [(':status', '100')]
            )
            self.assertTrue('END_STREAM' in frames[-1].flags)

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_respondWith400(self):
        """
        Triggering the call to _respondToBadRequestAndDisconnect leads to a
        400 error being sent automatically and the stream being torn down.
        """
        # The only "natural" way to trigger this in the current codebase is to
        # send a multipart/form-data request that the cgi module doesn't like.
        # That's absurdly hard, so instead we'll just call it ourselves. For
        # this reason we use the DummyProducerHandler, which doesn't write the
        # headers straight away.
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(self.getRequestHeaders, [], f)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request and the completion callback.
        stream = a.streams[1]
        request = stream._request
        cleanupCallback = a._streamCleanupCallbacks[1]

        # Abort the stream.
        stream._respondToBadRequestAndDisconnect()

        # This should have cancelled the request.
        self.assertTrue(request._disconnected)
        self.assertTrue(request.channel is None)

        # We expect 2 frames Settings and the 400 Headers.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            self.assertEqual(len(frames), 2)

            self.assertTrue(
                isinstance(frames[1], hyperframe.frame.HeadersFrame)
            )
            self.assertEqual(
                frames[1].data, [(':status', '400')]
            )
            self.assertTrue('END_STREAM' in frames[-1].flags)

        return cleanupCallback.addCallback(validate)


    def test_loseH2StreamConnection(self):
        """
        Calling L{Request.loseConnection} causes all data that has previously
        been sent to be flushed, and then the stream cleanly closed.
        """
        # Here we again want to use the DummyProducerHandler because it doesn't
        # close the connection on its own.
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(self.getRequestHeaders, [], f)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request.
        stream = a.streams[1]
        request = stream._request

        # Send in some writes.
        dataChunks = [b'hello', b'world', b'here', b'are', b'some', b'writes']
        for chunk in dataChunks:
            request.write(chunk)

        # Now lose the connection.
        request.loseConnection()

        # Check that the data was all written out correctly and that the stream
        # state is cleaned up.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Settings, Headers, 7 Data frames.
            self.assertEqual(len(frames), 9)
            self.assertTrue(all(f.stream_id == 1 for f in frames[1:]))

            self.assertTrue(
                isinstance(frames[1], hyperframe.frame.HeadersFrame)
            )
            self.assertTrue('END_STREAM' in frames[-1].flags)

            receivedDataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(
                receivedDataChunks,
                dataChunks + [b""],
            )

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_cannotRegisterTwoProducers(self):
        """
        The L{H2Stream} object forbids registering two producers.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(self.getRequestHeaders, [], f)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request.
        stream = a.streams[1]
        request = stream._request

        self.assertRaises(ValueError, stream.registerProducer, request, True)


    def test_handlesPullProducer(self):
        """
        L{Request} objects that have registered pull producers get blocked and
        unblocked according to HTTP/2 flow control.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyPullProducerHandler

        # Send the request.
        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Get the producer completion deferred and ensure we call
        # request.finish.
        stream = a.streams[1]
        request = stream._request
        producerComplete = request._actualProducer.result
        producerComplete.addCallback(lambda x: request.finish())

        # Check that the sending loop sends all the appropriate data.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(
                dataChunks,
                [
                    b"0", b"1", b"2", b"3", b"4", b"5",
                    b"6", b"7", b"8", b"9", b""
                ]
            )

        return a._streamCleanupCallbacks[1].addCallback(validate)



class H2FlowControlTests(unittest.TestCase):
    """
    Tests that ensure that we handle HTTP/2 flow control limits appropriately.
    """
    if skipH2:
        skip = skipH2


    getRequestHeaders = [
        (':method', 'GET'),
        (':authority', 'localhost'),
        (':path', '/'),
        (':scheme', 'https'),
        ('user-agent', 'twisted-test-code'),
    ]


    getResponseData = b"'''\nNone\n'''\n"


    postRequestHeaders = [
        (':method', 'POST'),
        (':authority', 'localhost'),
        (':path', '/post_endpoint'),
        (':scheme', 'https'),
        ('user-agent', 'twisted-test-code'),
        ('content-length', '25'),
    ]


    postRequestData = [b"hello ", b"world, ", b"it's ", b"http/2!"]


    postResponseData = b"'''\n25\nhello world, it's http/2!'''\n"


    def test_bufferExcessData(self):
        """
        When a L{Request} object is not using C{IProducer} to generate data and
        so is not having backpressure exerted on it, the L{H2Stream} object
        will buffer data until the flow control window is opened.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyHTTPHandler

        # Shrink the window to 5 bytes, then send the request.
        requestBytes = f.preamble()
        requestBytes += f.buildSettingsFrame(
            {h2.settings.INITIAL_WINDOW_SIZE: 5}
        ).serialize()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Send in WindowUpdate frames that open the window one byte at a time,
        # to repeatedly temporarily unbuffer data. 5 bytes will have already
        # been sent.
        bonusFrames = len(self.getResponseData) - 5
        for _ in range(bonusFrames):
            frame = f.buildWindowUpdateFrame(streamID=1, increment=1)
            a.dataReceived(frame.serialize())

        # Give the sending loop a chance to catch up!
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Put the Data frames together to confirm we're all good.
            actualResponseData = b''.join(
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            )
            self.assertEqual(self.getResponseData, actualResponseData)

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_producerBlockingUnblocking(self):
        """
        L{Request} objects that have registered producers get blocked and
        unblocked according to HTTP/2 flow control.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        # Shrink the window to 5 bytes, then send the request.
        requestBytes = f.preamble()
        requestBytes += f.buildSettingsFrame(
            {h2.settings.INITIAL_WINDOW_SIZE: 5}
        ).serialize()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request object.
        stream = a.streams[1]
        request = stream._request

        # Confirm that the stream believes the producer is producing.
        self.assertTrue(stream._producerProducing)

        # Write 10 bytes to the connection.
        request.write(b"helloworld")

        # The producer should have been paused.
        self.assertFalse(stream._producerProducing)
        self.assertEqual(request.producer.events, ['pause'])

        # Open the flow control window by 5 bytes. This should not unpause the
        # producer.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=1, increment=5).serialize()
        )
        self.assertFalse(stream._producerProducing)
        self.assertEqual(request.producer.events, ['pause'])

        # Open the connection window by 5 bytes as well. This should also not
        # unpause the producer.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=0, increment=5).serialize()
        )
        self.assertFalse(stream._producerProducing)
        self.assertEqual(request.producer.events, ['pause'])

        # Open it by five more bytes. This should unpause the producer.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=1, increment=5).serialize()
        )
        self.assertTrue(stream._producerProducing)
        self.assertEqual(request.producer.events, ['pause', 'resume'])

        # Write another 10 bytes, which should force us to pause again. When
        # written this chunk will be sent as one lot, simply because of the
        # fact that the sending loop is not currently running.
        request.write(b"helloworld")
        self.assertFalse(stream._producerProducing)
        self.assertEqual(request.producer.events, ['pause', 'resume', 'pause'])

        # Open the window wide and then complete the request.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=1, increment=50).serialize()
        )
        self.assertTrue(stream._producerProducing)
        self.assertEqual(
            request.producer.events,
            ['pause', 'resume', 'pause', 'resume']
        )
        request.unregisterProducer()
        request.finish()

        # Check that the sending loop sends all the appropriate data.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(
                dataChunks,
                [b"hello", b"world", b"helloworld", b""]
            )

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_flowControlExact(self):
        """
        Exactly filling the flow control window still blocks producers.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        # Shrink the window to 5 bytes, then send the request.
        requestBytes = f.preamble()
        requestBytes += f.buildSettingsFrame(
            {h2.settings.INITIAL_WINDOW_SIZE: 5}
        ).serialize()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request object.
        stream = a.streams[1]
        request = stream._request

        # Confirm that the stream believes the producer is producing.
        self.assertTrue(stream._producerProducing)

        # Write 10 bytes to the connection. This should block the producer
        # immediately.
        request.write(b"helloworld")
        self.assertFalse(stream._producerProducing)
        self.assertEqual(request.producer.events, ['pause'])

        # Despite the producer being blocked, write one more byte. This should
        # not get sent or force any other data to be sent.
        request.write(b"h")

        # Open the window wide and then complete the request.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=1, increment=50).serialize()
        )
        self.assertTrue(stream._producerProducing)
        self.assertEqual(
            request.producer.events,
            ['pause', 'resume']
        )
        request.unregisterProducer()
        request.finish()

        # Check that the sending loop sends all the appropriate data.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(dataChunks, [b"hello", b"world", b"h", b""])

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_endingBlockedStream(self):
        """
        L{Request} objects that end a stream that is currently blocked behind
        flow control can still end the stream and get cleaned up.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        # Shrink the window to 5 bytes, then send the request.
        requestBytes = f.preamble()
        requestBytes += f.buildSettingsFrame(
            {h2.settings.INITIAL_WINDOW_SIZE: 5}
        ).serialize()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request object.
        stream = a.streams[1]
        request = stream._request

        # Confirm that the stream believes the producer is producing.
        self.assertTrue(stream._producerProducing)

        # Write 10 bytes to the connection, then complete the connection.
        request.write(b"helloworld")
        request.unregisterProducer()
        request.finish()

        # This should have completed the request.
        self.assertTrue(request.finished)

        # Open the window wide and then complete the request.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=1, increment=50).serialize()
        )

        # Check that the sending loop sends all the appropriate data.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(
                dataChunks,
                [b"hello", b"world", b""]
            )

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_responseWithoutBody(self):
        """
        We safely handle responses without bodies.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()

        # We use the DummyProducerHandler just because we can guarantee that it
        # doesn't end up with a body.
        a.requestFactory = DummyProducerHandler

        # Send the request.
        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request object and the stream completion callback.
        stream = a.streams[1]
        request = stream._request
        cleanupCallback = a._streamCleanupCallbacks[1]

        # Complete the connection immediately.
        request.unregisterProducer()
        request.finish()

        # This should have completed the request.
        self.assertTrue(request.finished)

        # Check that the sending loop sends all the appropriate data.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            self.assertEqual(len(frames), 3)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(
                dataChunks,
                [b""],
            )

        return cleanupCallback.addCallback(validate)


    def test_windowUpdateForCompleteStream(self):
        """
        WindowUpdate frames received after we've completed the stream are
        safely handled.
        """
        # To test this with the data sending loop working the way it does, we
        # need to send *no* body on the response. That's unusual, but fine.
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()

        # We use the DummyProducerHandler just because we can guarantee that it
        # doesn't end up with a body.
        a.requestFactory = DummyProducerHandler

        # Send the request.
        requestBytes = f.preamble()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request object and the stream completion callback.
        stream = a.streams[1]
        request = stream._request
        cleanupCallback = a._streamCleanupCallbacks[1]

        # Complete the connection immediately.
        request.unregisterProducer()
        request.finish()

        # This should have completed the request.
        self.assertTrue(request.finished)

        # Now open the flow control window a bit. This should cause no
        # problems.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=1, increment=50).serialize()
        )

        # Check that the sending loop sends all the appropriate data.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            self.assertEqual(len(frames), 3)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(
                dataChunks,
                [b""],
            )

        return cleanupCallback.addCallback(validate)


    def test_producerUnblocked(self):
        """
        L{Request} objects that have registered producers that are not blocked
        behind flow control do not have their producer notified.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyProducerHandler

        # Shrink the window to 5 bytes, then send the request.
        requestBytes = f.preamble()
        requestBytes += f.buildSettingsFrame(
            {h2.settings.INITIAL_WINDOW_SIZE: 5}
        ).serialize()
        requestBytes += buildRequestBytes(
            self.getRequestHeaders, [], f
        )
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Grab the request object.
        stream = a.streams[1]
        request = stream._request

        # Confirm that the stream believes the producer is producing.
        self.assertTrue(stream._producerProducing)

        # Write 4 bytes to the connection, leaving space in the window.
        request.write(b"word")

        # The producer should not have been paused.
        self.assertTrue(stream._producerProducing)
        self.assertEqual(request.producer.events, [])

        # Open the flow control window by 5 bytes. This should not notify the
        # producer.
        a.dataReceived(
            f.buildWindowUpdateFrame(streamID=1, increment=5).serialize()
        )
        self.assertTrue(stream._producerProducing)
        self.assertEqual(request.producer.events, [])

        # Open the window wide complete the request.
        request.unregisterProducer()
        request.finish()

        # Check that the sending loop sends all the appropriate data.
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Grab the data from the frames.
            dataChunks = [
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            ]
            self.assertEqual(
                dataChunks,
                [b"word", b""]
            )

        return a._streamCleanupCallbacks[1].addCallback(validate)


    def test_unnecessaryWindowUpdate(self):
        """
        When a WindowUpdate frame is received for the whole connection but no
        data is currently waiting, nothing exciting happens.
        """
        f = FrameFactory()
        b = StringTransport()
        a = H2Connection()
        a.requestFactory = DummyHTTPHandler

        # Send the request.
        frames = buildRequestFrames(
            self.postRequestHeaders, self.postRequestData, f
        )
        frames.insert(1, f.buildWindowUpdateFrame(streamID=0, increment=5))
        requestBytes = f.preamble()
        requestBytes += b''.join(f.serialize() for f in frames)
        a.makeConnection(b)
        # one byte at a time, to stress the implementation.
        for byte in iterbytes(requestBytes):
            a.dataReceived(byte)

        # Give the sending loop a chance to catch up!
        def validate(streamID):
            buffer = FrameBuffer()
            buffer.receiveData(b.value())
            frames = list(buffer)

            # Check that the stream is correctly terminated.
            self.assertTrue('END_STREAM' in frames[-1].flags)

            # Put the Data frames together to confirm we're all good.
            actualResponseData = b''.join(
                f.data for f in frames
                if isinstance(f, hyperframe.frame.DataFrame)
            )
            self.assertEqual(self.postResponseData, actualResponseData)

        return a._streamCleanupCallbacks[1].addCallback(validate)
