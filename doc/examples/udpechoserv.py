
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"just twistd -y me"
from twisted.internet import main, udp
import pwd

class PacketPrinter:

    def packetReceived(self, data, addr, port):
        print "received", `data`, "from", `addr`
        port.socket.sendto(data, addr)
        
application = main.Application('udp-echo')
application.addPort(udp.Port(8080, PacketPrinter()))
