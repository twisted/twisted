
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
"""
Support module for making a port forwarder with mktap.
"""
from twisted.protocols import portforward
from twisted.python import usage
from twisted.application import strports

class Options(usage.Options):
    synopsis = "Usage: mktap portforward [options]"
    longdesc = 'Port Forwarder.'
    optParameters = [
          ["port", "p", "6666","Set the port number."],
          ["host", "h", "localhost","Set the host."],
          ["dest_port", "d", 6665,"Set the destination port."],
    ]

def makeService(config):
    f = portforward.ProxyFactory(config['host'], int(config['dest_port']))
    return strports.service(config['port'], f)
