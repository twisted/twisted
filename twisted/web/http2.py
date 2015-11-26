# -*- test-case-name: twisted.web.test.test_http2 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
HTTP2 Implementation

This is the basic server-side protocol implementation used by the Twisted
Web server for HTTP2.  This functionality is intended to be combined with the
HTTP/1.1 and HTTP/1.0 functionality in twisted.web.http to provide complete
protocol support for HTTP-type protocols.

Some function is currently missing here, including:

- handling flow control, both remote and local
- handling remote settings changes
- deciding on suitable local settings values
"""
from __future__ import absolute_import

from collections import deque

from zope.interface import implementer

import h2.connection
import h2.events

from twisted.internet.interfaces import (
    IProtocol, ITransport, IConsumer, IPushProducer
)
from twisted.internet.protocol import Protocol
from twisted.protocols.tls import _PullToPush



@implementer(IProtocol)
class H2Connection(Protocol):
    """
    A class representing a single HTTP/2 connection.

    This implementation of IProtocol works hand in hand with H2Stream. This is
    because we have the requirement to register multiple producers for a single
    HTTP/2 connection, one for each stream. The standard Twisted interfaces
    don't really allow for this, so instead there's a custom interface between
    the two objects that allows them to work hand-in-hand here.
    """
    factory = None
    site = None


    def __init__(self):
        self.conn = h2.connection.H2Connection(client_side=False)
        self.streams = {}


    # Implementation of IProtocol
    def connectionMade(self):
        """
        Called by the reactor when a connection is received. May also be called
        by the GenericHTTPChannel during upgrade to HTTP/2.
        """
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())


    def dataReceived(self, data):
        """
        Called whenever a chunk of data is received from the transport.

        @param data: The data received from the transport.
        @type data: C{bytes}
        """
        events = self.conn.receive_data(data)

        for event in events:
            # TODO: Consider replacing with dictionary-dispatch.
            if isinstance(event, h2.events.RequestReceived):
                self._requestReceived(event)
            elif isinstance(event, h2.events.DataReceived):
                self._requestDataReceived(event)
            elif isinstance(event, h2.events.StreamEnded):
                self._requestEnded(event)
            elif isinstance(event, h2.events.StreamReset):
                self._requestAborted(event)
            elif isinstance(event, h2.events.WindowUpdated):
                self._handleWindowUpdate(event)
            elif isinstance(event, h2.events.RemoteSettingsChanged):
                # TODO: Have a policy on settings changes.
                self.conn.acknowledge_settings(event)
            elif isinstance(event, h2.events.ConnectionTerminated):
                self.transport.loseConnection()

        dataToSend = self.conn.data_to_send()
        if dataToSend:
            self.transport.write(dataToSend)


    def connectionLost(self, reason):
        """
        Called when the transport connection is lost.

        Informs all outstanding response handlers that the connection has been
        lost.
        """
        for stream in self.streams.values():
            stream.connectionLost(reason)

        self.streams = {}


    # Internal functions.
    def _requestReceived(self, event):
        """
        Internal handler for when a request has been received.

        @param event: The Hyper-h2 event that encodes information about the
            received request.
        @type event: L{h2.events.RequestReceived}
        """
        stream = H2Stream(
            event.stream_id, self, event.headers, self.requestFactory
        )
        stream.site = self.site
        stream.factory = self.factory
        self.streams[event.stream_id] = stream


    def _requestDataReceived(self, event):
        """
        Internal handler for when a chunk of data is received for a given
        request.

        @param event: The Hyper-h2 event that encodes information about the
            received data.
        @type event: L{h2.events.DataReceived}
        """
        stream = self.streams[event.stream_id]
        stream.receiveDataChunk(event.data)


    def _requestEnded(self, event):
        """
        Internal handler for when a request is complete, and we expect no
        further data for that request.

        @param event: The Hyper-h2 event that encodes information about the
            completed stream.
        @type event: L{h2.events.StreamEnded}
        """
        stream = self.streams[event.stream_id]
        stream.requestComplete()


    def _requestAborted(self, event):
        """
        Internal handler for when a request is aborted by a remote peer.

        @param event: The Hyper-h2 event that encodes information about the
            reset stream.
        @type event: L{h2.events.StreamReset}
        """
        stream = self.streams[event.stream_id]
        stream.connectionLost("Stream reset")


    def writeHeaders(self, version, code, reason, headers, stream_id):
        """
        Called by C{Request} objects to write a complete set of HTTP headers to
        a stream.

        @param version: The HTTP version in use. Unused in HTTP/2.
        @type version: C{bytes}

        @param code: The HTTP status code to write.
        @type code: C{bytes}

        @param reason: The HTTP reason phrase to write. Unused in HTTP/2.
        @type reason: C{bytes}

        @param headers: The headers to write to the stream.
        @type headers: L{twisted.web.http_headers.Headers}

        @param stream_id: The ID of the stream to write the headers to.
        @type stream_id: C{int}
        """
        headers.insert(0, (b':status', code))
        self.conn.send_headers(stream_id, headers)
        self.transport.write(self.conn.data_to_send())


    def writeDataToStream(self, stream_id, data):
        """
        Called by L{H2Stream} objects to write response data to a given stream.
        Writes a single data frame.

        @param stream_id: The ID of the stream to write the data to.
        @type stream_id: C{int}

        @param data: The data chunk to write to the stream.
        @type data: C{bytes}
        """
        # TODO: This method needs substantial enhancement. Concerns are: flow
        # control, max frame sizes. For now, blindly assumes everything is
        # cool.
        self.conn.send_data(stream_id, data)
        self.transport.write(self.conn.data_to_send())


    def endRequest(self, stream_id):
        """
        Called by L{H2Stream} objects to signal completion of a response.

        @param stream_id: The ID of the stream to write the data to.
        @type stream_id: C{int}
        """
        self.conn.end_stream(stream_id)
        self.transport.write(self.conn.data_to_send())


    def requestDone(self, stream_id):
        """
        Called by a C{H2Stream} object to clean up whatever permanent state is
        in use.

        @param stream_id: The ID of the stream to clean up state for.
        @type stream_id: C{int}
        """
        del self.streams[stream_id]


    def _handleWindowUpdate(self, event):
        """
        Manage flow control windows.

        Streams that are blocked on flow control will register themselves with
        the connection. This will fire deferreds that wake those streams up and
        allow them to continue processing.
        """
        # TODO: Implement.
        pass


    def getPeer(self):
        """
        @see L{ITransport.getPeer}
        """
        return self.transport.getPeer()


    def getHost(self):
        """
        @see L{ITransport.getHost}
        """
        return self.transport.getHost()


    def openStreamWindow(self, stream_id, increment):
        """
        Open the stream window by a given increment.
        """
        # TODO: Consider whether we want some kind of consolidating logic here.
        self.conn.increment_flow_control_window(increment, stream_id=stream_id)
        self.conn.increment_flow_control_window(increment, stream_id=None)
        self.transport.write(self.conn.data_to_send())



@implementer(ITransport, IConsumer, IPushProducer)
class H2Stream(object):
    """
    A class representing a single HTTP/2 stream.

    This class works hand-in-hand with H2Connection. It acts to provide an
    implementation of ITransport, IConsumer, and IProducer that work for a
    single HTTP/2 connection, while tightly cleaving to the interface provided
    by those interfaces. It does this by having a tight coupling to
    H2Connection, which allows associating many of the functions of ITransport,
    IConsumer, and IProducer to objects on a stream-specific level.
    """
    def __init__(self, stream_id, connection, headers, requestFactory):
        self.stream_id = stream_id
        self.producing = False
        self.command = None
        self.path = None
        self.producer = None
        self._inboundDataBuffer = deque()
        self._conn = connection
        self._request = requestFactory(self, queued=False)

        self._convertHeaders(headers)

    def _convertHeaders(self, headers):
        """
        This method converts the HTTP/2 header set into something that looks
        like HTTP/1.1. In particular, it strips the 'special' headers and adds
        a Host: header.
        """
        gotLength = False

        for header in headers:
            if not header[0].startswith(b':'):
                gotLength = (
                    _addHeaderToRequest(self._request, header) or gotLength
                )
            elif header[0] == u':method':
                self.command = header[1].encode('utf-8')
            elif header[0] == u':path':
                self.path = header[1].encode('utf-8')
            elif header[0] == u':authority':
                # This is essentially the Host: header from HTTP/1.1
                _addHeaderToRequest(self._request, (u'host', header[1]))
            else:
                # There are only 4 acceptable special headers for requests.
                if not header[0] == u':scheme':
                    raise RuntimeError(
                        "Unexpected special header %r" % header[0]
                    )

        if not gotLength:
            self._request.gotLength(None)

        self._request.parseCookies()


    def receiveDataChunk(self, data):
        """
        Called when the connection has received a chunk of data from the
        underlying transport. If the stream has been registered with a
        consumer, and is currently able to push data, immediately passes it
        through. Otherwise, buffers the chunk until we can start producing.
        """
        if not self.producing:
            # Buffer data.
            self._inboundDataBuffer.append(data)
        else:
            self._request.handleContentChunk(data)
            self._conn.openStreamWindow(self.stream_id, len(data))


    def requestComplete(self):
        """
        Called by the L{H2Connection} when the all data for a request has been
        received. Currently, with the legacy Request object, just calls
        requestReceived.
        """
        self._request.requestReceived(self.command, self.path, b'HTTP/2')


    def connectionLost(self, reason):
        """
        Called by the L{H2Connection} when a connection is lost or a stream is
        reset.
        """
        self._request.connectionLost(reason)


    def writeHeaders(self, version, code, reason, headers):
        """
        Called by the consumer to write headers to the stream.
        """
        self._conn.writeHeaders(version, code, reason, headers, self.stream_id)


    def endRequest(self):
        """
        Called by the consumer when they've finished writing data.
        """
        self._conn.endRequest(self.stream_id)


    def requestDone(self, request):
        """
        Called by a consumer to clean up whatever permanent state is in use.
        """
        self._conn.requestDone(self.stream_id)


    # Implementation: ITransport
    def write(self, data):
        """
        Write a single chunk of data into a data frame.
        """
        # TODO: Buffering and flow control.
        # This should:
        #
        # - buffer if there's no room in the flow control window
        # - suspend a producer, if there is one.
        #
        # We also need a way for the H2Stream to register for flow control
        # updates.
        return self._conn.writeDataToStream(self.stream_id, data)


    def writeSequence(self, iovec):
        """
        Write a sequence of chunks of data into data frames.
        """
        for chunk in iovec:
            self.write(chunk)


    def loseConnection(self):
        """
        Close the connection after writing all pending data.
        """
        # TODO: How to signal early termination?
        self._conn.endRequest(self.stream_id)


    def getPeer(self):
        """
        Get information about the peer.
        """
        self._conn.getPeer()


    def getHost(self):
        """
        Similar to getPeer, but for this side of the connection.
        """
        self._conn.getHost()


    # Implementation: IConsumer
    def registerProducer(self, producer, streaming):
        """
        @see L{IConsumer.registerProducer}
        """
        if self.producer:
            raise ValueError(
                "registering producer %s before previous one (%s) was "
                "unregistered" % (producer, self.producer))

        if not streaming:
            producer = _PullToPush(producer, self)
            producer.startStreaming()

        self.producer = producer


    def unregisterProducer(self):
        """
        @see L{IConsumer.unregisterProducer}
        """
        # When the producer is unregistered, we're done.
        self.producer = None
        self.hasStreamingProducer = None

        # TODO: When is this an error case?
        #self.loseConnection()


    # Implementation: IPushProducer
    def stopProducing(self):
        """
        @see L{IProducer.stopProducing}
        """
        self.producing = False
        # TODO: How to signal abnormal termination?
        self.loseConnection()


    def pauseProducing(self):
        """
        @see L{IPushProducer.pauseProducing}
        """
        self.producing = False


    def resumeProducing(self):
        """
        @see L{IPushProducer.resumeProducing}
        """
        self.producing = True
        consumedLength = 0

        while self.producing and self._inboundDataBuffer:
            # Allow for pauseProducing to be called in response to a call to
            # resumeProducing.
            chunk = self._inboundDataBuffer.popleft()
            consumedLength += len(chunk)
            self._request.handleContentChunk(chunk)

        self._conn.openStreamWindow(self.stream_id, consumedLength)



def _addHeaderToRequest(request, header):
    """
    Add a header tuple to a request header object.
    """
    requestHeaders = request.requestHeaders
    name, value = header
    name, value = name.encode('utf-8'), value.encode('utf-8')
    values = requestHeaders.getRawHeaders(name)

    if values is not None:
        values.append(value)
    else:
        requestHeaders.setRawHeaders(name, [value])

    if name == b'content-length':
        request.gotLength(int(value))
        return True

    return False
