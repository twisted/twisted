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

import os, traceback

from twisted.python import usage
from twisted.protocols import dns

import server, authority

class Options(usage.Options):
    optParameters = [
        ["interface", "i", "",   "The interface to which to bind"],
        ["port",      "p", "53", "The port on which to listen"],
    ]
    
    optFlags = [
        ["cache",       "c", "Enable record caching"],
        ["recursive",   "r", "Perform recursive lookups"],
        ["verbose",     "v", "Log verbosely"]
    ]

    zones = None
    zonefiles = None
    
    def __init__(self):
        usage.Options.__init__(self)
        self['verbose'] = 0
        self.bindfiles = []
        self.zonefiles = []
    
    
    def opt_pyzone(self, filename):
        """Specify the filename of a Python syntax zone definition"""
        if not os.path.exists(filename):
            raise usage.UsageError(filename + ": No such file")
        self.zonefiles.append(filename)

    def opt_bindzone(self, filename):
        """Specify the filename of a BIND9 syntax zone definition"""
        if not os.path.exists(filename):
            raise usage.UsageError(filename + ": No such file")
        self.bindfiles.append(filename)


    def opt_verbose(self):
        """Increment verbosity level"""
        self['verbose'] += 1


    def postOptions(self):
        self.zones = []
        for f in self.zonefiles:
            try:
                self.zones.append(authority.PySourceAuthority(f))
            except Exception, e:
                traceback.print_exc()
                raise usage.UsageError("Invalid syntax in " + f)
        for f in self.bindfiles:
            try:
                self.zones.append(authority.BindAuthority(f))
            except Exception, e:
                traceback.print_exc()
                raise usage.UsageError("Invalid syntax in " + f)
        try:
            self['port'] = int(self['port'])
        except ValueError:
            raise usage.UsageError("Invalid port: %r" % (self['port'],))


def updateApplication(app, config):
    import client, cache

    ca, cl = [], []
    if config['cache']:
        ca.append(cache.CacheResolver(verbose=config['verbose']))
    if config['recursive']:
        cl.append(client.createResolver())

    f = server.DNSServerFactory(config.zones, ca, cl, config['verbose'])
    p = dns.DNSDatagramProtocol(f)
    f.noisy = 0

    app.listenUDP(config['port'], p)
    app.listenTCP(config['port'], f)
