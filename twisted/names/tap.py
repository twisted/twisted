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
Domain Name Server
"""

import os

from twisted.python import usage
from twisted.names import server
from twisted.protocols import dns

import traceback

class Options(usage.Options):
    optParameters = [
        ["interface", "i", "*",  "The interface to which to bind"],
        ["port",      "p", "53", "The port on which to listen"]
    ]

    zonefiles = None
    
    def __init__(self):
        usage.Options.__init__(self)
        self.zonefiles = []
    
    
    def opt_zonefile(self, filename):
        if not os.path.exists(filename):
            raise usage.UsageError(filename + ": No such file")
        self.zonefiles.append(filename)
    
    
    def postOptions(self):
        zones = []
        if not len(self.zonefiles):
            raise usage.UsageError("At least one zone file must be specified")
        for f in self.zonefiles:
            try:
                zones.append(server.Authority(f))
            except Exception, e:
                traceback.print_exc()
                raise usage.UsageError(e)
        if not len(zones):
            raise usage.UsageError("At least one zone file must contain a valid zone")
        self.zones = zones
        
        try:
            self['port'] = int(self['port'])
        except ValueError:
            raise usage.UsageError("Invalid port: %r" % (self['port'],))


def updateApplication(app, config):
    f = server.DNSServerFactory(config.zones)
    p = dns.DNSClientProtocol(f)
    app.listenUDP(config['port'], p)
    app.listenTCP(config['port'], f)
