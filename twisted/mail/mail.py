
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
from twisted.python import defer, components

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

class FileMessage:

    __implements__ = smtp.IMessage,

    def __init__(self, fp, name, finalName):
        self.fp = fp
        self.name = name
        self.finalName = finalName

    def lineReceived(self, line):
        self.fp.write(line+'\n')

    def eomReceived(self):
        self.fp.close()
        os.rename(self.name, self.finalName)
        deferred = defer.Deferred()
        deferred.callback(self.finalName)
        return deferred

    def connectionLost(self):
        self.fp.close()
        os.remove(self.name)


class IDomain(components.Interface):
    """An email domain."""


class MailService(service.Service):
    """An email service."""
    
    # path where email will be stored
    storagePath = "/tmp/changeme"
    
    def __init__(self, name, app):
        service.Service.__init__(self, name, app)
        self.domains = DomainWithDefaultDict({}, BounceDomain())
