# -*- test-case-name: twisted.test.test_mail -*-
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
from twisted.protocols import smtp, http
from twisted.cred import service
from twisted.python import components
from twisted.internet import defer

# Sibling imports
import protocols

# System imports
import os

class DomainWithDefaultDict:
    '''Simulate a dictionary with a default value for non-existing keys.
    '''
    def __init__(self, domains, default):
        self.domains = domains
        self.default = default

    def setDefaultDomain(self, domain):
        self.default = domain
    
    def has_key(self, name):
        return 1

    def fromkeys(klass, keys, value=None):
        d = klass()
        for k in keys:
            d[k] = value
        return d
    fromkeys = classmethod(fromkeys)

    def __contains__(self, name):
        return 1

    def __getitem__(self, name):
        return self.domains.get(name, self.default)

    def __setitem__(self, name, value):
        self.domains[name] = value
    
    def __delitem__(self, name):
        del self.domains[name]
    
    def __iter__(self):
        return iter(self.domains)
    
    def __len__(self):
        return len(self.domains)
    
    def __str__(self):
        return '<DomainWithDefaultsDict %s>' % (self.domains,)
    
    def __repr__(self):
        return 'DomainWithDefaultsDict(%s)>' % (self.domains,)
    
    def get(self, key, default=None):
        return self.domains.get(key, default)
    
    def copy(self):
        return DomainWithDefaultsDict(self.domains.copy(), self.default)
    
    def iteritems(self):
        return self.domains.iteritems()
    
    def iterkeys(self):
        return self.domains.iterkeys()
    
    def itervalues(self):
        return self.domains.itervalues()
    
    def keys(self):
        return self.domains.keys()
    
    def values(self):
        return self.domains.values()

    def items(self):
        return self.domains.items()

    def popitem(self):
        return self.domains.popitem()
    
    def update(self, other):
        return self.domains.update(other)
    
    def clear(self):
        return self.domains.clear()
    
    def setdefault(self, key, default):
        return self.domains.setdefault(key, default)

class IDomain(components.Interface):
    """An email domain."""

    def exists(self, user):
        """
        Check whether or not the specified user exists in this domain.
        
        @type user: C{twisted.protocols.smtp.User}
        @param user: The user to check
        
        @rtype: C{twisted.protocols.smtp.User}
        @return: C{user} or a C{Deferred} whose callback will be
        passed C{user}.
        
        @raise twisted.protocols.smtp.SMTPBadRcpt: Raised if the given
        user does not exist in this domain.
        """

    def willRelay(self, user, protocol):
        """Check whether or not we will pass on a message
        
        @type user: C{twisted.protocols.smtp.User}
        @param user: The user for whom the message is destined.
        
        @type protocol: C{twisted.internet.protocol.Protocol}
        @param protocol: The connection asking for the message to be relayed.
        
        @rtype: C{bool}
        @return: True if we will relay, false otherwise.
        """

    def addUser(self, user, password):
        """Add a username/password to this domain."""
    
    def startMessage(self, user):
        """Create and return a new message to be delivered to the given user.
        """

    def getCredentialsCheckers(self):
        """Return a list of ICredentialsChecker implementors for this domain.
        """

class BounceDomain:
    """A domain in which no user exists. 

    This can be used to block off certain domains.
    """

    __implements__ = (IDomain,)
    
    def exists(self, user):
        raise smtp.SMTPBadRcpt(user)
    
    def willRelay(self, user, protocol):
        return False
    
    def addUser(self, user, password):
        pass
    
    def startMessage(self, user):
        raise AssertionError, "No code should ever call this method for any reason"
    
    def getCredentialsCheckers(self):
        return []

class FileMessage:
    """A file we can write an email too."""
    
    __implements__ = smtp.IMessage

    def __init__(self, fp, name, finalName):
        self.fp = fp
        self.name = name
        self.finalName = finalName

    def lineReceived(self, line):
        self.fp.write(line+'\n')

    def eomReceived(self):
        self.fp.close()
        os.rename(self.name, self.finalName)
        return defer.succeed(self.finalName)

    def connectionLost(self):
        self.fp.close()
        os.remove(self.name)

class MailService(service.Service):
    """An email service."""

    queue = None
    domains = None
    portals = None

    def __init__(self, name):
        service.Service.__init__(self, name)
        self.domains = DomainWithDefaultDict({}, BounceDomain())
        self.portals = {}

    def getPOP3Factory(self):
        return protocols.POP3Factory(self)

    def getSMTPFactory(self):
        return protocols.SMTPFactory(self)

    def getESMTPFactory(self):
        return protocols.ESMTPFactory(self)

    def setQueue(self, queue):
        """Set the queue for outgoing emails."""
        self.queue = queue

    def lookupPortal(self, name):
        return self.portals[name]
    
    def defaultPortal(self):
        return self.portals['']
