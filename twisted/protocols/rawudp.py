# -*- test-case-name: twisted.test.test_rawudp -*-
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

"""Implementation of raw packet interfaces for UDP"""

import struct

from twisted.internet import protocol
from twisted.protocols import raw

class UDPHeader:
    def __init__(self, data):

        (self.source, self.dest, self.len, self.check) \
                 = struct.unpack("!HHHH", data[:8])

class RawUDPProtocol(protocol.AbstractDatagramProtocol):
    __implements__ = raw.IRawDatagramProtocol
    def __init__(self):
        self.udpProtos = {}

    def addProto(self, num, proto):
        if not isinstance(proto, protocol.DatagramProtocol):
            raise TypeError, 'Added protocol must be an instance of DatagramProtocol'
        if num < 0:
            raise TypeError, 'Added protocol must be positive or zero'
        if num >= 2**16:
            raise TypeError, 'Added protocol must fit in 16 bits'
        if num not in self.udpProtos:
            self.udpProtos[num] = []
        self.udpProtos[num].append(proto)

    def datagramReceived(self,
                         data,
                         partial,
                         source,
                         dest,
                         protocol,
                         version,
                         ihl,
                         tos,
                         tot_len,
                         fragment_id,
                         fragment_offset,
                         dont_fragment,
                         more_fragments,
                         ttl):
        header = UDPHeader(data)
        for proto in self.udpProtos.get(header.dest, ()):
            proto.datagramReceived(data[8:],
                                   (source, header.source))
