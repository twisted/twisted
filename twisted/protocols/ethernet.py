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
# -*- test-case-name: twisted.test.test_ethernet -*-

"""Support for working directly with ethernet frames"""

import struct


from twisted.internet import protocol
from twisted.protocols import raw
from twisted.python import components

class IEthernetProtocol(components.Interface):
    """An interface for protocols that handle Ethernet frames"""
    def addProto():
        """Add an IRawPacketProtocol protocol"""

    def datagramReceived():
        """An Ethernet frame has been received"""

class EthernetHeader:
    def __init__(self, data):

        (self.dest, self.source, self.proto) \
                    = struct.unpack("!6s6sH", data[:6+6+2])

class EthernetProtocol(protocol.AbstractDatagramProtocol):
    __implements__ = IEthernetProtocol
    def __init__(self):
        self.etherProtos = {}

    def addProto(self, num, proto):
        proto = raw.IRawPacketProtocol(proto)
        if num < 0:
            raise TypeError, 'Added protocol must be positive or zero'
        if num >= 2**16:
            raise TypeError, 'Added protocol must fit in 16 bits'
        if num not in self.etherProtos:
            self.etherProtos[num] = []
        self.etherProtos[num].append(proto)

    def datagramReceived(self, data, partial=0):
        header = EthernetHeader(data[:14])
        for proto in self.etherProtos.get(header.proto, ()):
            proto.datagramReceived(data=data[14:],
                                   partial=partial,
                                   dest=header.dest,
                                   source=header.source,
                                   protocol=header.proto)
