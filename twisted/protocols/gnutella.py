# Twisted, the Framework of Your Internet
# Copyright (C) 2002 Bryce "Zooko" O'Whielacronx
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

"""
Gnutella, v0.4
http://www9.limewire.com/developer/gnutella_protocol_0.4.pdf

This module is incomplete.  The "GnutellaTalker" class is complete but is completely untested.
The "GnutellaRouter" and "GnutellaServent" classes are yet to be written.
"""

# system imports
import random, re, string, struct

# twisted import
from twisted.protocols.basic import LineReceiver
from twisted.python import log

true = 1
false = 0

CONNSTRINGRE=re.compile("^GNUTELLA CONNECT/([^\r\n]*)")
CONNSTRING="GNUTELLA CONNECT/0.4"
ACKSTRING="GNUTELLA OK"

HEADERLENGTH=23
HEADERENCODING="<16sBBBI" # descriptorId, payloadDescriptor, ttl, hops, payloadLength

OURMAXPAYLOADLENGTH=640 * 2**10

PAYLOADLENGTHLENGTH=4
PAYLOADLENGTHOFFSET=HEADERLENGTH-PAYLOADLENGTHLENGTH
PAYLOADENCODING="<I" # payloadLength

PONGPAYLOADENCODING="<HBBBBII" # port, -- 4 octets of IPv4 address --, numberOfFilesShared, kbShared

PARTIALQUERYHITPAYLOADLENGTH=11
PARTIALQUERYHITPAYLOADENCODING="<BHBBBBI" # numberOfHits, port, -- 4 octets of IPv4 address --, speed
PARTIALQUERYHITRESULTLENGTH=8
PARTIALQUERYHITRESULTENCODING="<II" # fileIndex, fileSize

SERVENTIDENTIFIERENCODING="<16s" # serventIdentifier

PUSHPAYLOADENCODING="<16sIBBBBH" # serventIdentifier, fileIndex, -- 4 octets of IPv4 address --, port

payloadDescriptor2Name = {
    0x00: "Ping",
    0x01: "Pong",
    0x40: "Push",
    0x80: "Query",
    0x81: "QueryHit",
    }

def popTrailingNulls(s):
    while s[-1] == '\x00':
        s = s[:-1]
    return s

class GnutellaTalker(LineReceiver):
    """
    This just speaks the Gnutella protocol and translates it into Python methods for higher-level services to program with.
    You probably want a higher-level class like GnutellaRouter or GnutellaServent.

    If you really want to use this class itself, then the way to use it is to subclass it and override the methods named {ping,pong,push,query,queryHit}Received().

    One constraint that it imposes which is not specified in the Gnutella 0.4 spec is that payload lengths must be less than or equal to 640 KB.  If the payload length is greater than that, GnutellaTalker closes the connection.
    """
    def __init__(self):
        self.handshake = "start" # state transitions: "start" -> "hesaidhello", "hesaidhello" -> "completed", "start" -> "isaidhello", "isaidhello" -> "completed"
        self.gotver = None
        self.secret = "geheim"

        self.buf = ''

    def setSecret(self, secret):
        self.secret = secret

    # METHODS OF INTEREST TO CLIENTS (including subclasses)
    def sendPing(self, ttl):
        self.transport.write(struct.pack(HEADERENCODING, ""))
        ### XXXX incomplete.  Zooko stopped here to go to bed after the first night of hacking this file.  --Zooko 2002-07-15

    # METHODS OF INTEREST TO SUBCLASSES
    def pingReceived(self, descriptorId, ttl, hops):
        """
        Override this to handle ping messages.
        """
        log.msg("%s.pingReceived(%s, %s, %s)" % (str(self), str(descriptorId), str(ttl), str(hops),))
        pass
    
    def pongReceived(self, descriptorId, ttl, hops, ipAddress, port, numberOfFilesShared, kbShared):
        """
        Override this to handle pong messages.

        @param ipAddress a string representing an IPv4 address like this "140.184.83.37"; This is the representation that the Python Standard Library's socket.connect() expects.
        @param port an integer port number
        @param numberOfFilesShared a long
        @param kbShared a long
        """
        log.msg("%s.pongReceived(%s, %s, %s, ipAddress=%s, port=%s, numberOfFilesShared=%s, kbShared=%s)" % (str(self), str(descriptorId), str(ttl), str(hops), str(ipAddress), str(port), str(numberOfFilesShared), str(kbShared), ))
        pass

    def queryReceived(self, descriptorId, ttl, hops, searchCriteria, minimumSpeed):
        """
        Override this to handle query messages.
        
        @param searchCriteria a string
        @param minimumSpeed integer KB/s -- you are not supposed to respond to this query if you can't serve at least this fast
        """
        log.msg("%s.queryReceived(%s, %s, %s, searchCriteria=%s, minimumSpeed=%s" % (str(self), str(descriptorId), str(ttl), str(hops), str(searchCriteria), str(minimumSpeed),))
        pass
                                                                                          
    def queryHitReceived(self, descriptorId, ttl, hops, ipAddress, port, resultSet, serventIdentifer, speed):
        """
        Override this to handle query hit messages.
        
        @param ipAddress a string representing an IPv4 address like this "140.184.83.37"; This is the representation that the Python Standard Library's socket.connect() expects.
        @param port an integer port number
        @param resultSet a list of tuples of (fileIndex, fileSize, fileName,) where fileIndex is a long, fileSize (in bytes) is a long, and fileName is a string
        @param serventIdentifier string of length 16
        @param speed integer KB/s claimed by the responding host
        """
        log.msg("%s.queryHitReceived(%s, %s, %s, ipAddress=%s, port=%s, resultSet=%s, serventIdentifier=%s, speed=%s" % (str(self), str(descriptorId), str(ttl), str(hops), str(ipAddress), str(port), str(resultSet), str(serventIdentifier), str(speed),))
        pass
    
    def pushReceived(descriptorId, ttl, hops, ipAddress, port, serventIdentifer, fileIndex):
        """
        Override this to handle push messages.
        
        @param ipAddress a string representing an IPv4 address like this "140.184.83.37"; This is the representation that the Python Standard Library's socket.connect() expects.
        @param port an integer port number
        @param serventIdentifier string of length 16
        @param fileIndex a long
        """
        log.msg("%s.pushReceived(%s, %s, %s, ipAddress=%s, port=%s, serventIdentifier=%s, fileIndex=%s" % (str(self), str(descriptorId), str(ttl), str(hops), str(ipAddress), str(port), str(serventIdentifier), str(fileIndex),))
        pass
    
    # METHODS OF INTEREST TO THIS CLASS ONLY
    def abortConnection(self, logmsg):
        log.msg(logmsg + ", self: %s" % str(self))
        self.transport.loseConnection()
        return

    def handlePing(self, descriptorId, ttl, hops, payload):
        """
        A ping message has arrived.
        """
        if payload != '':
            self.abortConnection("Received non-empty Ping payload.  Closing connection.  payload: %s" % str(payload))
            return 

        self.pingReceived(descriptorId, ttl, hops)

    def handlePong(self, descriptorId, ttl, hops, payload):
        try:
            (port, ipA0, ipA1, ipA2, ipA3, numberOfFilesShared, kbShared,) = struct.unpack(PONGPAYLOADENCODING, payload)
        except struct.error, le:
            self.abortConnection("Received ill-formatted Pong payload.  Closing connection.  payload: %s" % str(payload))
            return

        ipAddress = string.join(map(str, (ipA0, ipA1, ipA2, ipA3,)), '.')
        self.pongReceived(descriptorId, ttl, hops, ipAddress, port, numberOfFilesShared, kbShared)

    def handleQuery(self, descriptorId, ttl, hops, payload):
        try:
            (minimumSpeed,) = struct.unpack("<H", payload[:2])
        except struct.error, le:
            self.abortConnection("Received ill-formatted Query payload.  Closing connection.  payload: %s" % str(payload))
            return
        searchCriteria = payload[2:]
        self.queryReceived(descriptorId, ttl, hops, searchCriteria, minimumSpeed)

    def handleQueryHit(self, descriptorId, ttl, hops, payload):
        try:
            (numberOfHits, port, ipA0, ipA1, ipA2, ipA3, speed,) = struct.unpack(PARTIALQUERYHITPAYLOADENCODING, payload[:PARTIALQUERYHITPAYLOADLENGTH])
        except struct.error, le:
            self.abortConnection("Received ill-formatted QueryHit payload.  Closing connection.  payload: %s" % str(payload))
            return
        resultSet = []
        i = PARTIALQUERYHITPAYLOADLENGTH
        end = len(payload) - SERVENTIDENTIFIERLENGTH
        while i < end:
            try:
                (fileIndex, fileSize,) = struct.unpack(PARTIALQUERYHITRESULTENCODING, payload[i:i+PARTIALQUERYHITRESULTLENGTH])
            except struct.error, le:
                self.abortConnection("Received ill-formatted partial QueryHit result.  Closing connection.  partial query hit result: %s" % str(payload[i:i+PARTIALQUERYHITRESULTLENGTH]))
                return
            p += PARTIALQUERYHITRESULTLENGTH
            nuli = string.find(payload, '\x00', p, end)
            if nuli == -1:
                fileName = payload[p:end]
                p = end
                log.msg("Found unterminated filename in query hit result.  Using it anyway.  self: %s, filename: %s" % (str(self), str(fileName),))
            else:
                fileName = popTrailingNulls(payload[p:nuli])
                # XXX The following lines cause us to skip over any BearShare-style Extended Query Hit Descriptor stuff.  --Zooko 2002-07-15
                p = string.find(payload, '\x00', nuli+1, end) + 1
                if p == 0:
                    p = end

            resultSet.append((fileIndex, fileSize, fileName,))

        assert i == end, "internal error: i != end after the query hit descriptor result reader loop.  self: %s, i: %s, end: %s, unprocessed part of query hit result set: %s" % (str(self), str(i), str(end), str(payload[i:end]),)
        if len(resultSet) != numberOfHits:
            log.msg("Found wrong number of results in result set.  Using the results we found anyway.  self: %s, numberOfHits: %s, len(resultSet): %s" % (str(self), str(numberOfHits), str(len(resultSet)),))

        try:
            (serventIdentifier,) = struct.unpack(SERVENTIDENTIFIERENCODING, payload[i:])
        except struct.error, le:
            self.abortConnection("Received ill-formatted QueryHit payload.  Closing connection.  i: %s, ill-formed part of query hit payload: %s" % (str(i), str(payload[i:]),))
            return

        ipAddress = string.join(map(str, (ipA0, ipA1, ipA2, ipA3,)), '.')
        self.queryHitReceived(descriptorId, ttl, hops, ipAddress, port, resultSet, serventIdentifer, speed)
         
    def handlePush(self, descriptorId, ttl, hops, payload):
        try:
            (serventIdentifer, fileIndex, ipA0, ipA1, ipA2, ipA3, port,) = struct.unpack(PUSHPAYLOADENCODING, payload)
        except struct.error, le:
            self.abortConnection("Received ill-formatted Push payload.  Closing connection.  i: %s, ill-formed part of query hit payload: %s" % (str(i), str(payload[i:]),))
            return
        ipAddress = string.join(map(str, (ipA0, ipA1, ipA2, ipA3,)), '.')
        self.pushReceived(descriptorId, ttl, hops, ipAddress, port, serventIdentifer, fileIndex)

    def descriptorReceived(self, descriptor):
        """
        A Gnutella descriptor has arrived.

        @precondition descriptor must be a string of the right length to hold a payload of the encoded length.: len(descriptor) == (struct.unpack(PAYLOADENCODING, descriptors[PAYLOADLENGTHOFFSET:HEADERLENGTH])[0] + HEADERLENGTH): "self: %s, descriptor: %s" % (str(self), str(descriptor),)
        """
        assert len(descriptor) == (struct.unpack(PAYLOADENCODING, descriptors[PAYLOADLENGTHOFFSET:HEADERLENGTH])[0] + HEADERLENGTH), "precondition failure: descriptor must be a string of the right length to hold a payload of the encoded length." + " -- " + "self: %s, descriptor: %s" % (str(self), str(descriptor),)
                                                                                          
        try:
            (descriptorId, payloadDescriptor, ttl, hops, payloadLength,) = struct.unpack(HEADERENCODING, descriptor[:HEADERLENGTH])
        except struct.error, le:
            self.abortConnection("Received ill-formatted descriptor.  Closing connection.  payload: %s" % str(descriptor))
            return

        name = payloadDescriptor2Name.get(payloadDescriptor)
        if name is None:
            self.abortConnection("Received unrecognized payload descriptor.  Closing connection.  payloadDescriptor: %s" % str(payloadDescriptor))
            return 

        handlermeth = getattr(self, "handle" + name)
        assert callable(handlermeth), "internal error: didn't find handler for this descriptor.  self: %s, name: %s" % (str(self), str(name),)
        payload = descriptor[HEADERLENGTH+payloadLength:]
        handlermeth(descriptorId, ttl, hops, payload)

    def lineReceived(self, line):
        """
        @precondition We must be expecting a GNUTELLA CONNECT handshake move.: self.handshake in ("start", "isaidhello",): "self.handshake: %s, line: %s" % (str(self.handshake), str(line),)
        """
        assert self.handshake in ("start", "isaidhello",), "precondition failure: We must be expecting a GNUTELLA CONNECT handshake move." + "--" + "self.handshake: %s, line: %s" % (str(self.handshake), str(line),)

        if self.handshake == "start":
            mo = CONNSTRINGRE.match(line)
            if not mo:
                self.abortConnection("Received incorrect GNUTELLA HELLO.  Closing connection.  line: %s" % str(line))
                return 

            self.handshake = "completed"
            self.gotver = mo.group(1)
            self.sendLine(ACKSTRING)
            self.setRawMode()
        else:
            assert self.handshake == "isaidhello"
            if line != ACKSTRING:
                self.abortConnection("Received incorrect GNUTELLA OK.  Closing connection.  line: %s" % str(line))
                return 
            self.handshake = "completed"
            self.setRawMode()

    def rawDataReceived(self, data):
        self.buf += data # XXX opportunity for future optimization  --Zooko 2002-07-15
        if len(self.buf) >= HEADERLENGTH:
            try:
                (payloadLength,) = struct.unpack(PAYLOADENCODING, self.buf[PAYLOADLENGTHOFFSET:HEADERLENGTH])
            except struct.error, le:
                self.abortConnection("Received ill-formatted raw data.  Closing connection.  self.buf: %s" % str(self.buf))
                return
            if (payloadLength > OURMAXPAYLOADLENGTH) or (payloadLength < 0):
                # 640 KB ought to be enough for anybody...
                self.abortConnection("Received payload > %d KB or < than 0 in size.  Closing connection.  payloadLength: %s" % ((OURMAXPAYLOADLENGTH / 2**10), str(payloadLength),))
                return
            descriptorlength = HEADERLENGTH + payloadLength
            if len(self.buf) >= descriptorlength:
                descriptor, self.buf = self.buf[:descriptorlength], self.buf[descriptorlength:]
                self.descriptorReceived(descriptor)

class GnutellaRouter(GnutellaTalker):
    """
    This is a well-behaved Gnutella servent that routes messages as it should.  It does not, however, serve any actual files.
    If you want to run a Gnutella servent that serves files, try the GnutellaServent class.  If you want to use GnutellaRouter for something, subclass it and override the methods named {ping,pong,push,query,queryHit}Received().  But please remember that you have to call GnutellaRouter's `pingReceived()' from your overridden `pingReceived()' if you want it to route the ping!
    """
    def __init__(self):
        GnutellaTalker.__init__(self)
        ### XXXX incomplete.  Zooko stopped here to go to bed after the first night of hacking this file.  --Zooko 2002-07-15

