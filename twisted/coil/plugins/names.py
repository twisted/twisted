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

"""Coil plugin for twisted.names DNS server."""

# Twisted Imports
from twisted.coil import coil
from twisted.names import dns
from twisted.python import roots, components

# System Imports
import types, string


class SimpleDomainConfigurator(coil.Configurator):
    """Configurator for SimpleDomains."""
    
    configurableClass = dns.SimpleDomain
    
    configTypes = {"ip" : [types.StringType, "IP Address", ""]}
    
    def getConfiguration(self):
        return {'ip': string.join(map(str, map(ord, self.instance.ip)), '.')}
    
    def config_ip(self, ip):
        self.instance.ip = dns.IPtoBytes(ip)

def simpleDomainFactory(container, name):
    return dns.SimpleDomain(name, "127.0.0.1")

coil.registerConfigurator(SimpleDomainConfigurator, simpleDomainFactory)


class DNSServerConfigurator(coil.Configurator, coil.ConfigCollection):
    """Configurator for DNS server."""
    
    __implements__ = (coil.IConfigurator, coil.IConfigCollection)
    
    entityType = dns.IDomain
    
    configurableClass = dns.DNSServerFactory
    
    def __init__(self, instance):
        coil.Configurator.__init__(self, instance)
        coil.ConfigCollection.__init__(self, instance.boss.domains)


def dnsServerFactory(container, name):
    return dns.DNSServerFactory()

coil.registerConfigurator(DNSServerConfigurator, dnsServerFactory)
components.registerAdapter(DNSServerConfigurator, dns.DNSServerFactory, coil.IConfigCollection)
