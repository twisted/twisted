
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

"""Mail support for twisted python.
"""

# Twisted imports
from twisted.protocols import protocol, pop3, smtp
from twisted.cred import service
from twisted.manhole import coil
from twisted.python import roots

# Sibling imports
import maildir

# System imports
import types
import os


def createDomainsFactory(protocol_handler, domains):
    '''create a factory with a given protocol handler and a domains attribute

    Return a Factory with a Protocol given as the first argument,
    and a 'domains' attribute given as the second.
    The 'domains' argument should have a [] operator and .has_key method.
    '''
    ret = protocol.Factory()
    ret.protocol = protocol_handler
    ret.domains = domains
    return ret


class POP3Factory(protocol.ServerFactory, coil.Configurable):
    """Protocol for POP3 servers."""
    
    protocol = pop3.VirtualPOP3
    configName = "POP3 Server"
    configCreatable = 0

coil.registerClass(POP3Factory)


class SMTPFactory(protocol.ServerFactory, coil.Configurable):
    """Protocol for SMTP servers."""
    
    protocol = smtp.DomainSMTP
    configName = "SMTP Server"
    configCreatable = 0

coil.registerClass(SMTPFactory)


class MailService(service.Service, coil.Configurable, roots.Homogenous):
    """An email service.
    
    Also, a collection of domains.
    """
    
    entityType = maildir.AbstractMaildirDomain
    
    # path where email will be stored
    storagePath = "/tmp/changeme"
    
    def __init__(self, name, app):
        service.Service.__init__(self, name, app)
        self.domains = DomainWithDefaultDict({}, BounceDomain())
        self.entities = self.domains.domains # for roots.Homogenous
        self._setConfigDispensers()
    
    # Configuration stuff.
    def _setConfigDispensers(self):
        self.configDispensers = [
            ['makePOP3Server', POP3Factory, "POP3 server %s" % self.serviceName],
            ['makeSMTPServer', SMTPFactory, "SMTP server for %s" % self.serviceName]
            ]

    def makePOP3Server(self):
        f = POP3Factory()
        f.domains = self.domains
        return f
    
    def makeSMTPServer(self):
        f = SMTPFactory()
        f.domains = self.domains
        return f
    
    def configInit(self, container, name):
        self.__init__(name, container.app)

    def getConfiguration(self):
        return {"name": self.serviceName,
                "storagePath": self.storagePath}

    configTypes = {
        'name': types.StringType,
        'storagePath': types.StringType,
        }

    configName = 'Twisted Mail Service'

    def config_name(self, name):
        raise coil.InvalidConfiguration("You can't change a Service's name.")

    def config_storagePath(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
        self.storagePath = path

coil.registerClass(MailService)


class DomainWithDefaultDict:
    '''Simulate a dictionary with a default value for non-existing keys.
    '''
    def __init__(self, domains, default):
        self.domains = domains
        self.default = default

    def has_key(self, name):
        return 1

    def __getitem__(self, name):
        return self.domains.get(name, self.default)

    def __setitem__(self, name, value):
        self.domains[name] = value


class BounceDomain:
    """A domain in which no user exists. 

    This can be used to block off certain domains.
    """
    def exists(self, user, success, failure):
        """No user exists in a BounceDomain -- always return 0
        """
        failure(user)
