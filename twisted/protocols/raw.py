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

"""Interface definitions for working with raw packets"""

from twisted.internet import protocol
from twisted.python import components

class IRawDatagramProtocol(components.Interface):
    """An interface for protocols such as UDP, ICMP and TCP."""

    def addProto():
        """
        Add a protocol on top of this one.
        """

    def datagramReceived():
        """
        An IP datagram has been received. Parse and process it.
        """

class IRawPacketProtocol(components.Interface):
    """An interface for low-level protocols such as IP and ARP."""

    def addProto():
        """
        Add a protocol on top of this one.
        """

    def datagramReceived():
        """
        An IP datagram has been received. Parse and process it.
        """
