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
# -*- test-case-name: twisted.test.test_ip -*-

"""Support for working directly with IP packets"""

import struct
import socket

from twisted.internet import protocol
from twisted.protocols import raw
from twisted.python import components

class IPHeader:
    def __init__(self, data):

        (ihlversion, self.tos, self.tot_len, self.fragment_id, frag_off,
         self.ttl, self.protocol, self.check, saddr, daddr) \
         = struct.unpack("!BBHHHBBH4s4s", data[:20])
        self.saddr = socket.inet_ntoa(saddr)
        self.daddr = socket.inet_ntoa(daddr)
        self.version = ihlversion & 0x0F
        self.ihl = ((ihlversion & 0xF0) >> 4) << 2
        self.fragment_offset = frag_off & 0x1FFF
        self.dont_fragment = (frag_off & 0x4000 != 0)
        self.more_fragments = (frag_off & 0x2000 != 0)

MAX_SIZE = 2L**32

class IPProtocol(protocol.AbstractDatagramProtocol):
    __implements__ = raw.IRawPacketProtocol

    def __init__(self):
        self.ipProtos = {}

    def addProto(self, num, proto):
        proto = raw.IRawDatagramProtocol(proto)
        if num < 0:
            raise TypeError, 'Added protocol must be positive or zero'
        if num >= MAX_SIZE:
            raise TypeError, 'Added protocol must fit in 32 bits'
        if num not in self.ipProtos:
            self.ipProtos[num] = []
        self.ipProtos[num].append(proto)

    def datagramReceived(self,
                         data,
                         partial,
                         dest,
                         source,
                         protocol):
        header = IPHeader(data)
        for proto in self.ipProtos.get(header.protocol, ()):
            proto.datagramReceived(data=data[20:],
                                   partial=partial,
                                   source=header.saddr,
                                   dest=header.daddr,
                                   protocol=header.protocol,
                                   version=header.version,
                                   ihl=header.ihl,
                                   tos=header.tos,
                                   tot_len=header.tot_len,
                                   fragment_id=header.fragment_id,
                                   fragment_offset=header.fragment_offset,
                                   dont_fragment=header.dont_fragment,
                                   more_fragments=header.more_fragments,
                                   ttl=header.ttl,
                                   )
