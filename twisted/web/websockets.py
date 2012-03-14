# -*- test-case-name: twisted.web.test.test_websockets -*-
# Copyright (c) 2011-2012 Oregon State University Open Source Lab
#               2011-2012 Corbin Simpson
#                    2012 Twisted Matrix Laboratories
#
# See LICENSE for details.

"""
The WebSockets protocol (RFC 6455), provided as a resource which wraps a
factory.
"""

from base64 import b64encode, b64decode
from hashlib import sha1
from struct import pack, unpack

from twisted.protocols.policies import ProtocolWrapper, WrappingFactory
from twisted.python import log
from twisted.web.error import NoResource
from twisted.web.resource import IResource
from twisted.web.server import NOT_DONE_YET
from zope.interface import implements

class WSException(Exception):
    """
    Something stupid happened here.

    If this class escapes txWS, then something stupid happened in multiple
    places.
    """

# Control frame specifiers. Some versions of WS have control signals sent
# in-band. Adorable, right?

NORMAL, CLOSE, PING, PONG = range(4)

opcode_types = {
    0x0: NORMAL,
    0x1: NORMAL,
    0x2: NORMAL,
    0x8: CLOSE,
    0x9: PING,
    0xa: PONG,
}

opcode_for_type = {
    NORMAL: 0x1,
    CLOSE: 0x8,
    PING: 0x9,
    PONG: 0xa,
}

encoders = {
    "base64": b64encode,
}

decoders = {
    "base64": b64decode,
}

# Authentication for WS.

def make_accept(key):
    """
    Create an "accept" response for a given key.

    This dance is expected to somehow magically make WebSockets secure.
    """

    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    return sha1("%s%s" % (key, guid)).digest().encode("base64").strip()

# Frame helpers.
# Separated out to make unit testing a lot easier.
# Frames are bonghits in newer WS versions, so helpers are appreciated.

def mask(buf, key):
    """
    Mask or unmask a buffer of bytes with a masking key.

    The key must be exactly four bytes long.
    """

    # This is super-secure, I promise~
    key = [ord(i) for i in key]
    buf = list(buf)
    for i, char in enumerate(buf):
        buf[i] = chr(ord(char) ^ key[i % 4])
    return "".join(buf)

def make_hybi07_frame(buf, opcode=NORMAL):
    """
    Make a HyBi-07 frame.

    This function always creates unmasked frames, and attempts to use the
    smallest possible lengths.
    """

    if len(buf) > 0xffff:
        length = "\x7f%s" % pack(">Q", len(buf))
    elif len(buf) > 0x7d:
        length = "\x7e%s" % pack(">H", len(buf))
    else:
        length = chr(len(buf))

    # Always make a normal packet.
    header = chr(0x80 | opcode_for_type[opcode])
    frame = "%s%s%s" % (header, length, buf)
    return frame

def parse_hybi07_frames(buf):
    """
    Parse HyBi-07 frames in a highly compliant manner.
    """

    start = 0
    frames = []

    while True:
        # If there's not at least two bytes in the buffer, bail.
        if len(buf) - start < 2:
            break

        # Grab the header. This single byte holds some flags nobody cares
        # about, and an opcode which nobody cares about.
        header = ord(buf[start])
        if header & 0x70:
            # At least one of the reserved flags is set. Pork chop sandwiches!
            raise WSException("Reserved flag in HyBi-07 frame (%d)" % header)
            frames.append(("", CLOSE))
            return frames, buf

        # Get the opcode, and translate it to a local enum which we actually
        # care about.
        opcode = header & 0xf
        try:
            opcode = opcode_types[opcode]
        except KeyError:
            raise WSException("Unknown opcode %d in HyBi-07 frame" % opcode)

        # Get the payload length and determine whether we need to look for an
        # extra length.
        length = ord(buf[start + 1])
        masked = length & 0x80
        length &= 0x7f

        # The offset we're gonna be using to walk through the frame. We use
        # this because the offset is variable depending on the length and
        # mask.
        offset = 2

        # Extra length fields.
        if length == 0x7e:
            if len(buf) - start < 4:
                break

            length = buf[start + 2:start + 4]
            length = unpack(">H", length)[0]
            offset += 2
        elif length == 0x7f:
            if len(buf) - start < 10:
                break

            # Protocol bug: The top bit of this long long *must* be cleared;
            # that is, it is expected to be interpreted as signed. That's
            # fucking stupid, if you don't mind me saying so, and so we're
            # interpreting it as unsigned anyway. If you wanna send exabytes
            # of data down the wire, then go ahead!
            length = buf[start + 2:start + 10]
            length = unpack(">Q", length)[0]
            offset += 8

        if masked:
            if len(buf) - (start + offset) < 4:
                break

            key = buf[start + offset:start + offset + 4]
            offset += 4

        if len(buf) - (start + offset) < length:
            break

        data = buf[start + offset:start + offset + length]

        if masked:
            data = mask(data, key)

        if opcode == CLOSE:
            if len(data) >= 2:
                # Gotta unpack the opcode and return usable data here.
                data = unpack(">H", data[:2])[0], data[2:]
            else:
                # No reason given; use generic data.
                data = 1000, "No reason given"

        frames.append((opcode, data))
        start += offset + length

    return frames, buf[start:]

class WebSocketsProtocol(ProtocolWrapper):
    """
    Protocol which wraps another protocol to provide a WebSockets transport
    layer.
    """

    buf = ""
    codec = None

    def __init__(self, *args, **kwargs):
        ProtocolWrapper.__init__(self, *args, **kwargs)
        self.pending_frames = []

    def connectionMade(self):
        ProtocolWrapper.connectionMade(self)
        log.msg("Opening connection with %s" % self.transport.getPeer())

    def parseFrames(self):
        """
        Find frames in incoming data and pass them to the underlying protocol.
        """

        try:
            frames, self.buf = parse_hybi07_frames(self.buf)
        except WSException:
            # Couldn't parse all the frames, something went wrong, let's bail.
            log.err()
            self.loseConnection()
            return

        for frame in frames:
            opcode, data = frame
            if opcode == NORMAL:
                # Business as usual. Decode the frame, if we have a decoder.
                if self.codec:
                    data = decoders[self.codec](data)
                # Pass the frame to the underlying protocol.
                ProtocolWrapper.dataReceived(self, data)
            elif opcode == CLOSE:
                # The other side wants us to close. I wonder why?
                reason, text = data
                log.msg("Closing connection: %r (%d)" % (text, reason))

                # Close the connection.
                self.loseConnection()
                return
            elif opcode == PING:
                # 5.5.2 PINGs must be responded to with PONGs.
                # 5.5.3 PONGs must contain the data that was sent with the
                # provoking PING.
                self.transport.write(make_hybi07_frame(data, opcode=PONG))

    def sendFrames(self):
        """
        Send all pending frames.
        """

        for frame in self.pending_frames:
            # Encode the frame before sending it.
            if self.codec:
                frame = encoders[self.codec](frame)
            packet = make_hybi07_frame(frame)
            self.transport.write(packet)
        self.pending_frames = []

    def dataReceived(self, data):
        self.buf += data

        self.parseFrames()

        # Kick any pending frames. This is needed because frames might have
        # started piling up early; we can get write()s from our protocol above
        # when they makeConnection() immediately, before our browser client
        # actually sends any data. In those cases, we need to manually kick
        # pending frames.
        if self.pending_frames:
            self.sendFrames()

    def write(self, data):
        """
        Write to the transport.

        This method will only be called by the underlying protocol.
        """

        self.pending_frames.append(data)
        self.sendFrames()

    def writeSequence(self, data):
        """
        Write a sequence of data to the transport.

        This method will only be called by the underlying protocol.
        """

        self.pending_frames.extend(data)
        self.sendFrames()

    def loseConnection(self):
        """
        Close the connection.

        This includes telling the other side we're closing the connection.

        If the other side didn't signal that the connection is being closed,
        then we might not see their last message, but since their last message
        should, according to the spec, be a simple acknowledgement, it
        shouldn't be a problem.
        """

        # Send a closing frame. It's only polite. (And might keep the browser
        # from hanging.)
        if not self.disconnecting:
            frame = make_hybi07_frame("", opcode=CLOSE)
            self.transport.write(frame)

            ProtocolWrapper.loseConnection(self)

class WebSocketsFactory(WrappingFactory):
    """
    Factory which wraps another factory to provide WebSockets frames for all
    of its protocols.

    This factory does not provide the HTTP headers required to perform a
    WebSockets handshake; see C{WebSocketsResource}.
    """

    protocol = WebSocketsProtocol

class WebSocketsResource(object):
    """
    A resource for serving a protocol through WebSockets.

    This class wraps a factory and connects it to WebSockets clients. Each
    connecting client will be connected to a new protocol of the factory.

    Due to unresolved questions of logistics, this resource cannot have
    children.
    """

    implements(IResource)

    isLeaf = True

    def __init__(self, factory):
        self._factory = WebSocketsFactory(factory)

    def getChildWithDefault(self, name, request):
        return NoResource("No such child resource.")

    def putChild(self, path, child):
        pass

    def render(self, request):
        """
        Render a request.

        We're not actually rendering a request. We are secretly going to
        handle a WebSockets connection instead.
        """

        # If we fail at all, we're gonna fail with 400 and no response.
        # You might want to pop open the RFC and read along.
        failed = False

        if request.method != "GET":
            # 4.2.1.1 GET is required.
            failed = True

        upgrade = request.getHeader("Upgrade")
        if upgrade is None or "websocket" not in upgrade.lower():
            # 4.2.1.3 Upgrade: WebSocket is required.
            failed = True

        connection = request.getHeader("Connection")
        if connection is None or "upgrade" not in connection.lower():
            # 4.2.1.4 Connection: Upgrade is required.
            failed = True

        key = request.getHeader("Sec-WebSocket-Key")
        if key is None:
            # 4.2.1.5 The challenge key is required.
            failed = True

        version = request.getHeader("Sec-WebSocket-Version")
        if version != "13":
            # 4.2.1.6 Only version 13 works.
            failed = True
            # 4.4 Forward-compatible version checking.
            request.setHeader("Sec-WebSocket-Version", "13")

        # Check whether a codec is needed. WS calls this a "protocol" for
        # reasons I cannot fathom. The specification permits multiple,
        # comma-separated codecs to be listed, but this functionality isn't
        # used in the wild. (If that ever changes, we'll have already added
        # the requisite codecs here anyway.) The main reason why we check for
        # codecs at all is that older draft versions of WebSockets used base64
        # encoding to work around the inability to send \x00 bytes, and those
        # runtimes would request base64 encoding during the handshake. We
        # stand prepared to engage that behavior should any of those runtimes
        # start supporting RFC WebSockets.
        #
        # We probably should remove this altogether, but I'd rather leave it
        # because it will prove to be a useful reference if/when extensions
        # are added, and it *does* work as advertised.
        codec = request.getHeader("Sec-WebSocket-Protocol")

        if codec:
            if codec not in encoders or codec not in decoders:
                log.msg("Codec %s is not implemented" % codec)
                failed = True

        if failed:
            request.setResponseCode(400)
            return ""

        # We are going to finish this handshake. We will return a valid status
        # code.
        # 4.2.2.5.1 101 Switching Protocols
        request.setResponseCode(101)
        # 4.2.2.5.2 Upgrade: websocket
        request.setHeader("Upgrade", "WebSocket")
        # 4.2.2.5.3 Connection: Upgrade
        request.setHeader("Connection", "Upgrade")
        # 4.2.2.5.4 Response to the key challenge
        request.setHeader("Sec-WebSocket-Accept", make_accept(key))
        # 4.2.2.5.5 Optional codec declaration
        if codec:
            request.setHeader("Sec-WebSocket-Protocol", codec)

        # Create the protocol. This could fail, in which case we deliver an
        # error status. Status 502 was decreed by glyph; blame him.
        protocol = self._factory.buildProtocol(request.transport.getPeer())
        if not protocol:
            request.setResponseCode(502)
            return ""
        if codec:
            protocol.codec = codec

        # Provoke request into flushing headers and finishing the handshake.
        request.write("")

        # And now take matters into our own hands. We shall manage the
        # transport's lifecycle.
        transport, request.transport = request.transport, None

        # Connect the transport to our factory, and make things go. We need to
        # do some stupid stuff here; see #3204, which could fix it.
        transport.protocol = protocol
        protocol.makeConnection(transport)

        return NOT_DONE_YET

__all__ = ("WebSocketsResource",)
