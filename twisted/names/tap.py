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
from twisted.application import internet, service

from twisted.names import server
from twisted.names import authority
from twisted.names import secondary

class Options(usage.Options):
    optParameters = [
        ["interface", "i", "",   "The interface to which to bind"],
        ["port",      "p", "53", "The port on which to listen"],
        ["resolv-conf", None, None,
            "Override location of resolv.conf (implies --recursive)"],
    ]

    optFlags = [
        ["cache",       "c", "Enable record caching"],
        ["recursive",   "r", "Perform recursive lookups"],
        ["iterative",   "I", "Perform lookups using the root servers"],
        ["verbose",     "v", "Log verbosely"]
    ]

    zones = None
    zonefiles = None

    def __init__(self):
        usage.Options.__init__(self)
        self['verbose'] = 0
        self.bindfiles = []
        self.zonefiles = []
        self.secondaries = []


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


    def opt_secondary(self, ip_domain):
        """Act as secondary for the specified domain, performing
        zone transfers from the specified IP (IP/domain)
        """
        args = ip_domain.split('/', 1)
        if len(args) != 2:
            raise usage.UsageError("Argument must be of the form IP/domain")
        self.secondaries.append((args[0], [args[1]]))

    def opt_verbose(self):
        """Increment verbosity level"""
        self['verbose'] += 1


    def postOptions(self):
        if self['resolv-conf']:
            self['recursive'] = True
        if self['iterative'] and self['recursive']:
            raise usage.UsageError("--iterative and --recursive are mutually exclusive.")

        self.svcs = []
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
        for f in self.secondaries:
            self.svcs.append(secondary.SecondaryAuthorityService(*f))
            self.zones.append(self.svcs[-1].getAuthority())
        try:
            self['port'] = int(self['port'])
        except ValueError:
            raise usage.UsageError("Invalid port: %r" % (self['port'],))


def makeService(config):
    import client, cache

    ca, cl = [], []
    if config['cache']:
        ca.append(cache.CacheResolver(verbose=config['verbose']))
    if config['recursive']:
        cl.append(client.createResolver(resolvconf=config['resolv-conf']))

    f = server.DNSServerFactory(config.zones, ca, cl, config['verbose'])
    p = dns.DNSDatagramProtocol(f)
    f.noisy = 0
    ret = service.MultiService()
    for (klass, arg) in [(internet.TCPServer, f), (internet.UDPServer, p)]:
        s = klass(config['port'], arg, interface=config['interface'])
        s.setServiceParent(ret)
    for svc in config.svcs:
        svc.setServiceParent(ret)
    return ret
