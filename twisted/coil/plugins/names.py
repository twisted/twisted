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
from twisted.coil import app, coil
from twisted.names import dns
from twisted.python import roots

# System Imports
import types, string


class Domain:
    """Dummy class for domains."""

class DomainConfigurator(coil.Configurator):
    """Base class for domain configurators."""

    configurableClass = Domain


class SimpleDomainConfigurator(DomainConfigurator):
    """Configurator for SimpleDomains."""
    
    configurableClass = dns.SimpleDomain
    
    configTypes = {"ip" : [types.StringType, "IP Address", ""]}
    
    def getConfiguration(self):
        return {'ip': string.join(map(str, map(ord, self.instance.ip)), '.')}
    
    def config_ip(self, ip):
        self.instance.ip = dns.IPtoBytes(ip)

def simpleDomainFactory(container, name):
    return dns.SimpleDomain(name, "127.0.0.1")


coil.registerConfigurator(DomainConfigurator, None)
coil.registerConfigurator(SimpleDomainConfigurator, simpleDomainFactory)


class DNSServerConfigurator(app.ProtocolFactoryConfigurator, roots.Homogenous):
    """Configurator for DNS server."""
    
    entityType = Domain
    
    configurableClass = dns.DNSServerFactory
    
    def __init__(self, instance):
        app.ProtocolFactoryConfigurator.__init__(self, instance)
        roots.Homogenous.__init__(self, instance.boss.domains)

    def entityConstraint(self, entity):
        # Domain class is not superclass of all domain classes, so we need to
        # check that the configurator for an added entity is an instance of
        # a DomainConfigurator subclass.
        return isinstance(coil.getConfigurator(entity), DomainConfigurator)


def dnsServerFactory(container, name):
    return dns.DNSServerFactory()

coil.registerConfigurator(DNSServerConfigurator, dnsServerFactory)
