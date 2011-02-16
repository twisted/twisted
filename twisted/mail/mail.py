# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Mail support for twisted python.
"""

# Twisted imports
from twisted.internet import defer
from twisted.application import service, internet
from twisted.python import util
from twisted.python import log

from twisted import cred
import twisted.cred.portal

# Sibling imports
from twisted.mail import protocols, smtp

# System imports
import os
from zope.interface import implements, Interface


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
        """
        Return a string describing the underlying domain mapping of this
        object.
        """
        return '<DomainWithDefaultDict %s>' % (self.domains,)


    def __repr__(self):
        """
        Return a pseudo-executable string describing the underlying domain
        mapping of this object.
        """
        return 'DomainWithDefaultDict(%s)' % (self.domains,)


    def get(self, key, default=None):
        return self.domains.get(key, default)

    def copy(self):
        return DomainWithDefaultDict(self.domains.copy(), self.default)

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

class IDomain(Interface):
    """An email domain."""

    def exists(user):
        """
        Check whether or not the specified user exists in this domain.

        @type user: C{twisted.protocols.smtp.User}
        @param user: The user to check

        @rtype: No-argument callable
        @return: A C{Deferred} which becomes, or a callable which
        takes no arguments and returns an object implementing C{IMessage}.
        This will be called and the returned object used to deliver the
        message when it arrives.

        @raise twisted.protocols.smtp.SMTPBadRcpt: Raised if the given
        user does not exist in this domain.
        """

    def addUser(user, password):
        """Add a username/password to this domain."""

    def startMessage(user):
        """Create and return a new message to be delivered to the given user.

        DEPRECATED.  Implement validateTo() correctly instead.
        """

    def getCredentialsCheckers():
        """Return a list of ICredentialsChecker implementors for this domain.
        """

class IAliasableDomain(IDomain):
    def setAliasGroup(aliases):
        """Set the group of defined aliases for this domain

        @type aliases: C{dict}
        @param aliases: Mapping of domain names to objects implementing
        C{IAlias}
        """

    def exists(user, memo=None):
        """
        Check whether or not the specified user exists in this domain.

        @type user: C{twisted.protocols.smtp.User}
        @param user: The user to check

        @type memo: C{dict}
        @param memo: A record of the addresses already considered while
        resolving aliases.  The default value should be used by all
        external code.

        @rtype: No-argument callable
        @return: A C{Deferred} which becomes, or a callable which
        takes no arguments and returns an object implementing C{IMessage}.
        This will be called and the returned object used to deliver the
        message when it arrives.

        @raise twisted.protocols.smtp.SMTPBadRcpt: Raised if the given
        user does not exist in this domain.
        """

class BounceDomain:
    """A domain in which no user exists.

    This can be used to block off certain domains.
    """

    implements(IDomain)

    def exists(self, user):
        raise smtp.SMTPBadRcpt(user)

    def willRelay(self, user, protocol):
        return False

    def addUser(self, user, password):
        pass

    def startMessage(self, user):
        """
        No code should ever call this function.
        """
        raise NotImplementedError(
                "No code should ever call this method for any reason")

    def getCredentialsCheckers(self):
        return []


class FileMessage:
    """A file we can write an email too."""

    implements(smtp.IMessage)

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


class MailService(service.MultiService):
    """An email service."""

    queue = None
    domains = None
    portals = None
    aliases = None
    smtpPortal = None

    def __init__(self):
        service.MultiService.__init__(self)
        # Domains and portals for "client" protocols - POP3, IMAP4, etc
        self.domains = DomainWithDefaultDict({}, BounceDomain())
        self.portals = {}

        self.monitor = FileMonitoringService()
        self.monitor.setServiceParent(self)
        self.smtpPortal = cred.portal.Portal(self)

    def getPOP3Factory(self):
        return protocols.POP3Factory(self)

    def getSMTPFactory(self):
        return protocols.SMTPFactory(self, self.smtpPortal)

    def getESMTPFactory(self):
        return protocols.ESMTPFactory(self, self.smtpPortal)

    def addDomain(self, name, domain):
        portal = cred.portal.Portal(domain)
        map(portal.registerChecker, domain.getCredentialsCheckers())
        self.domains[name] = domain
        self.portals[name] = portal
        if self.aliases and IAliasableDomain.providedBy(domain):
            domain.setAliasGroup(self.aliases)

    def setQueue(self, queue):
        """Set the queue for outgoing emails."""
        self.queue = queue

    def requestAvatar(self, avatarId, mind, *interfaces):
        if smtp.IMessageDelivery in interfaces:
            a = protocols.ESMTPDomainDelivery(self, avatarId)
            return smtp.IMessageDelivery, a, lambda: None
        raise NotImplementedError()

    def lookupPortal(self, name):
        return self.portals[name]

    def defaultPortal(self):
        return self.portals['']


class FileMonitoringService(internet.TimerService):

    def __init__(self):
        self.files = []
        self.intervals = iter(util.IntervalDifferential([], 60))

    def startService(self):
        service.Service.startService(self)
        self._setupMonitor()

    def _setupMonitor(self):
        from twisted.internet import reactor
        t, self.index = self.intervals.next()
        self._call = reactor.callLater(t, self._monitor)

    def stopService(self):
        service.Service.stopService(self)
        if self._call:
            self._call.cancel()
            self._call = None

    def monitorFile(self, name, callback, interval=10):
        try:
            mtime = os.path.getmtime(name)
        except:
            mtime = 0
        self.files.append([interval, name, callback, mtime])
        self.intervals.addInterval(interval)

    def unmonitorFile(self, name):
        for i in range(len(self.files)):
            if name == self.files[i][1]:
                self.intervals.removeInterval(self.files[i][0])
                del self.files[i]
                break

    def _monitor(self):
        self._call = None
        if self.index is not None:
            name, callback, mtime = self.files[self.index][1:]
            try:
                now = os.path.getmtime(name)
            except:
                now = 0
            if now > mtime:
                log.msg("%s changed, notifying listener" % (name,))
                self.files[self.index][3] = now
                callback(name)
        self._setupMonitor()
