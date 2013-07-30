# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Mail service support.
"""

# Twisted imports
from twisted.internet import defer
from twisted.application import service, internet
from twisted.python import util
from twisted.python import log
from twisted.cred.portal import Portal

# Sibling imports
from twisted.mail import protocols, smtp

# System imports
import os
from zope.interface import implements, Interface


class DomainWithDefaultDict:
    """
    A simulated dictionary for mapping domain names to domain objects with
    a default value for non-existing keys.

    @ivar domains: See L{__init__}
    @ivar default: See L{__init__}
    """

    def __init__(self, domains, default):
        """
        @type domains: C{dict} of C{str} -> L{IDomain} provider
        @param domains: A mapping of domain name to domain object.

        @type default: L{IDomain} provider
        @param default: The default domain.
        """
        self.domains = domains
        self.default = default


    def setDefaultDomain(self, domain):
        """
        Set the default domain.

        @type domain: L{IDomain} provider
        @param domain: The default domain.
        """
        self.default = domain


    def has_key(self, name):
        """
        Test for the presence of a domain name in this dictionary.

        This always returns C{True} because a default value will be returned
        if the name doesn't exists in this dictionary.

        @type name: C{str}
        @param name: A domain name.

        @rtype: C{bool}
        @return: C{True} to indicate that the domain name is in this
            dictionary.
        """
        return 1


    def fromkeys(klass, keys, value=None):
        """
        Create a new L{DomainWithDefaultDict} with the specified keys.

        @type keys: iterable of C{str}
        @param keys: Domain names to serve as keys in the new dictionary.

        @type value: C{NoneType} or L{IDomain} provider
        @param value: (optional) A domain object to serve as the value for all
            new keys in the dictionary.

        @rtype: L{DomainWithDefaultDict}
        @return: A new dictionary.
        """
        d = klass()
        for k in keys:
            d[k] = value
        return d
    fromkeys = classmethod(fromkeys)


    def __contains__(self, name):
        """
        Test for the presence of a domain name in this dictionary.

        This always returns C{True} because a default value will be returned
        if the name doesn't exists in this dictionary.

        @type name: C{str}
        @param name: A domain name.

        @rtype: C{bool}
        @return: C{True} to indicate that the domain name is in this
            dictionary.
        """
        return 1


    def __getitem__(self, name):
        """
        Look up a domain name and, if it is present, return the domain object
        associated with it.  Otherwise return the default domain.

        @type name: C{str}
        @param name: A domain name.

        @rtype: L{IDomain} provider or C{NoneType}
        @return: A domain object.
        """
        return self.domains.get(name, self.default)


    def __setitem__(self, name, value):
        """
        Associate a domain object with a domain name in this dictionary.

        @type name: C{str}
        @param name: A domain name.

        @type value: L{IDomain} provider
        @param value: A domain object.
        """
        self.domains[name] = value


    def __delitem__(self, name):
        """
        Delete the entry for a domain name in this dictionary.

        @type name: C{str}
        @param name: A domain name.
        """
        del self.domains[name]


    def __iter__(self):
        """
        Return an iterator over the domain names in this dictionary.

        @rtype: C{iterator} over C{str}
        @return: An iterator over the domain names.
        """
        return iter(self.domains)


    def __len__(self):
        """
        Return the number of domains in this dictionary.

        @rtype: C{int}
        @return: The number of domains in this dictionary.
        """
        return len(self.domains)


    def __str__(self):
        """
        Build an informal string representation of this dictionary.

        @rtype: C{str}
        @return: A string containing the mapping of domain names to domain
            objects.
        """
        return '<DomainWithDefaultDict %s>' % (self.domains,)


    def __repr__(self):
        """
        Build an "official" string representation of this dictionary.

        @rtype: C{str}
        @return: A pseudo-executable string describing the underlying domain
            mapping of this object.
        """
        return 'DomainWithDefaultDict(%s)' % (self.domains,)


    def get(self, key, default=None):
        """
        Look up a domain name in this dictionary.

        @type key: C{str}
        @param key: A domain name.

        @type default: L{IDomain} provider or C{NoneType}
        @param default: (optional) A domain object to be returned if the
            domain name is not in this dictionary.

        @rtype: L{IDomain} provider or C{NoneType}
        @return: The domain object associated with the domain name if it is in
            this dictionary.  Otherwise, the default value.
        """
        return self.domains.get(key, default)


    def copy(self):
        """
        Make a copy of this dictionary.

        @rtype: L{DomainWithDefaultDict}
        @return: A copy of this dictionary.
        """
        return DomainWithDefaultDict(self.domains.copy(), self.default)


    def iteritems(self):
        """
        Return an iterator over the domain name/domain object pairs in the
        dictionary.

        Using the returned iterator while adding or deleting entries from the
        dictionary may result in a C{RuntimeError} or failing to iterate over
        all the domain name/domain object pairs.

        @rtype: C{iterator} over (C{str}, L{IDomain} provider or C{NoneType})
        @return: An iterator over the domain name/domain object pairs.
        """
        return self.domains.iteritems()


    def iterkeys(self):
        """
        Return an iterator over the domain names in this dictionary.

        Using the returned iterator while adding or deleting entries from the
        dictionary may result in a C{RuntimeError} or failing to iterate over
        all the domain names.

        @rtype: C{iterator} over C{str}
        @return: An iterator over the domain names.
        """
        return self.domains.iterkeys()


    def itervalues(self):
        """
        Return an iterator over the domain objects in this dictionary.

        Using the returned iterator while adding or deleting entries from the
        dictionary may result in a C{RuntimeError} or failing to iterate over
        all the domain objects.

        @rtype: C{iterator} over L{IDomain} provider or C{NoneType}
        @return: An iterator over the domain objects.
        """
        return self.domains.itervalues()


    def keys(self):
        """
        Return a list of all domain names in this dictionary.

        @rtype: C{list} of C{str}
        @return: The domain names in this dictionary.

        """
        return self.domains.keys()


    def values(self):
        """
        Return a list of all domain objects in this dictionary.

        @rtype: C{list} of L{IDomain} provider or C{NoneType}
        @return: The domain objects in this dictionary.
        """
        return self.domains.values()


    def items(self):
        """
        Return a list of all domain name/domain object pairs in this dictionary.

        @rtype: C{list} of (C{str}, L{IDomain} provider or C{NoneType})
        @return: Domain name/domain object pairs in this dictionary.
        """
        return self.domains.items()


    def popitem(self):
        """
        Remove a random domain name/domain object pair from this dictionary and
        return it as a tuple.

        @rtype: (C{str}, L{IDomain} provider or C{NoneType})
        @return: A domain name/domain object pair.

        @raise KeyError: When this dictionary is empty.
        """
        return self.domains.popitem()


    def update(self, other):
        """
        Update this dictionary with domain name/domain object pairs from
        another dictionary.

        When this dictionary contains a domain name which is in the other
        dictionary, its value will be overwritten.

        @type other: C{dict} of C{str} -> L{IDomain} provider or C{NoneType}
        @param other: Another dictionary of domain name/domain object pairs.

        @rtype: C{NoneType}
        @return: None.
        """
        return self.domains.update(other)


    def clear(self):
        """
        Remove all items from this dictionary.

        @rtype: C{NoneType}
        @return: None.
        """
        return self.domains.clear()


    def setdefault(self, key, default):
        """
        Return the domain object associated with the domain name if it is
        present in this dictionary. Otherwise, set the value for the
        domain name to the default and return that value.

        @type key: C{str}
        @param key: A domain name.

        @type default: L{IDomain} provider
        @param default: A domain object.

        @rtype: L{IDomain} provider or C{NoneType}
        @return: The domain object associated with the domain name.
        """
        return self.domains.setdefault(key, default)



class IDomain(Interface):
    """
    An interface for email domains.
    """

    def exists(user):
        """
        Check whether a user exists in this domain.

        @type user: L{User}
        @param user: A user.

        @rtype: no-argument callable which returns an L{smtp.IMessage} provider
        @return: A function which takes no arguments and returns a message
            receiver for the user.

        @raise SMTPBadRcpt: When the given user does not exist in this domain.
        """


    def addUser(user, password):
        """
        Add a user to this domain.

        @type user: C{str}
        @param user: A username.

        @type password: C{str}
        @param password: A password.
        """


    def getCredentialsCheckers():
        """
        Return credentials checkers for this domain.

        @rtype: C{list} of L{ICredentialsChecker} provider
        @return: Credentials checkers for this domain.
        """



class IAliasableDomain(IDomain):
    """
    An interface for email domains which can be aliased to other domains.
    """

    def setAliasGroup(aliases):
        """
        Set the group of defined aliases for this domain.

        @type aliases: C{dict} of C{str} -> L{IAlias} provider
        @param aliases: A mapping of domain name to alias.
        """


    def exists(user, memo=None):
        """
        Check whether a user exists in this domain.

        @type user: L{User}
        @param user: A user.

        @type memo: C{NoneType} or C{dict} of L{AliasBase}
        @param memo: (optional) A record of the addresses already considered
            while resolving aliases.  The default value should be used by all
            external code.

        @rtype: no-argument callable which returns an L{smtp.IMessage} provider
        @return: A function which takes no arguments and returns a message
            receiver for the user.

        @raise SMTPBadRcpt: When the given user does not exist in this domain.
        """



class BounceDomain:
    """
    A domain with no users.

    This can be used to block off a domain.
    """

    implements(IDomain)

    def exists(self, user):
        """
        Raise an exception to indicate that the user does not exist in this
        domain.

        @type user: L{User}
        @param user: A user.

        @raise SMTPBadRcpt: When the given user does not exist in this domain.
        """
        raise smtp.SMTPBadRcpt(user)


    def willRelay(self, user, protocol):
        """
        Indicate that this domain will not relay.

        @type user: L{Address}
        @param user: The destination address.

        @type protocol: L{Protocol}
        @param protocol: The protocol over which the message to be relayed is
            being received.

        @rtype: C{bool}
        @return: C{False}.
        """
        return False


    def addUser(self, user, password):
        """
        Ignore attempts to add a user to this domain.

        @type user: C{str}
        @param user: A username.

        @type password: C{str}
        @param password: A password.
        """
        pass


    def getCredentialsCheckers(self):
        """
        Return no credentials checkers for this domain.

        @rtype: C{list}
        @return: The empty list.
        """
        return []



class FileMessage:
    """
    A message receiver which delivers content to a file.

    @ivar fp: See L{__init__}.
    @ivar name: See L{__init__}.
    @ivar finalName: See L{__init__}.
    """

    implements(smtp.IMessage)

    def __init__(self, fp, name, finalName):
        """
        @type fp: file-like object
        @param fp: The file in which to store the message while it is being
            received.

        @type name: C{str}
        @param name: The full path name of the temporary file.

        @type finalName: C{str}
        @param finalName: The full path name that should be given to the file
            holding the message after it has been fully received.
        """
        self.fp = fp
        self.name = name
        self.finalName = finalName


    def lineReceived(self, line):
        """
        Write a received line to the file.

        @type line: C{str}
        @param line: A received line.
        """
        self.fp.write(line+'\n')


    def eomReceived(self):
        """
        At the end of message, rename the file holding the message to its
        final name.

        @rtype: L{Deferred} which successfully results in a C{str}
        @return: A deferred which returns the final name of the file.
        """
        self.fp.close()
        os.rename(self.name, self.finalName)
        return defer.succeed(self.finalName)


    def connectionLost(self):
        """
        Delete the file holding the partially received message.
        """
        self.fp.close()
        os.remove(self.name)



class MailService(service.MultiService):
    """
    An email service.

    @type queue: L{Queue} or C{NoneType}
    @ivar queue: A queue for outgoing messages.

    @type domains: C{dict} of C{str} -> L{IDomain} provider
    @ivar domains: A mapping of supported domain name to domain object.

    @type portals: C{dict} of C{str} -> L{Portal}
    @ivar portals: A mapping of domain name to authentication portal.

    @type aliases: C{NoneType} or C{dict} of C{str} -> L{IAlias} provider
    @ivar aliases: A mapping of domain name to alias.

    @type smtpPortal: L{Portal}
    @ivar smtpPortal: A portal for authentication for the SMTP server.

    @type monitor: L{FileMonitoringService}
    @ivar monitor: A service to monitor changes to files.
    """

    queue = None
    domains = None
    portals = None
    aliases = None
    smtpPortal = None

    def __init__(self):
        """
        Initialize the mail service.
        """
        service.MultiService.__init__(self)
        # Domains and portals for "client" protocols - POP3, IMAP4, etc
        self.domains = DomainWithDefaultDict({}, BounceDomain())
        self.portals = {}

        self.monitor = FileMonitoringService()
        self.monitor.setServiceParent(self)
        self.smtpPortal = Portal(self)


    def getPOP3Factory(self):
        """
        Create a POP3 protocol factory.

        @rtype: L{POP3Factory}
        @return: A POP3 protocol factory.
        """
        return protocols.POP3Factory(self)


    def getSMTPFactory(self):
        """
        Create an SMTP protocol factory.

        @rtype: L{protocols.SMTPFactory}
        @return: An SMTP protocol factory.
        """
        return protocols.SMTPFactory(self, self.smtpPortal)


    def getESMTPFactory(self):
        """
        Create an ESMTP protocol factory.

        @rtype: L{protocols.ESMTPFactory}
        @return: An ESMTP protocol factory.
        """
        return protocols.ESMTPFactory(self, self.smtpPortal)


    def addDomain(self, name, domain):
        """
        Add a domain for which the service will accept email.

        @type name: C{str}
        @param name: A domain name.

        @type domain: L{IDomain} provider
        @param domain: A domain object.
        """
        portal = Portal(domain)
        map(portal.registerChecker, domain.getCredentialsCheckers())
        self.domains[name] = domain
        self.portals[name] = portal
        if self.aliases and IAliasableDomain.providedBy(domain):
            domain.setAliasGroup(self.aliases)


    def setQueue(self, queue):
        """
        Set the queue for outgoing emails.

        @type queue: L{Queue}
        @param queue: A queue for outgoing messages.
        """
        self.queue = queue


    def requestAvatar(self, avatarId, mind, *interfaces):
        """
        Return a message delivery for an authenticated SMTP user.

        @type avatarId: C{str}
        @param avatarId: A string which identifies an authenticated user.

        @type mind: C{NoneType}
        @param mind: Unused.

        @type interfaces: C{n-tuple} of C{Interface}
        @param interfaces: A group of interfaces one of which the avatar must
            support.

        @rtype: (L{IMessageDelivery}, L{ESMTPDomainDelivery}, no-argument
            callable)
        @return: A tuple of the supported interface, a message delivery, and
            a logout function.

        @raise NotImplementedError: When the given interfaces do not include
            L{IMessageDelivery}.
        """
        if smtp.IMessageDelivery in interfaces:
            a = protocols.ESMTPDomainDelivery(self, avatarId)
            return smtp.IMessageDelivery, a, lambda: None
        raise NotImplementedError()


    def lookupPortal(self, name):
        """
        Find the portal for a domain.

        @type name: C{str}
        @param name: A domain name.

        @rtype: L{Portal}
        @return: A portal.
        """
        return self.portals[name]


    def defaultPortal(self):
        """
        Return the portal for the default domain.

        The default domain is named ''.

        @rtype: L{Portal}
        @return: The portal for the default domain.
        """
        return self.portals['']



class FileMonitoringService(internet.TimerService):
    """
    A service for monitoring changes to files.

    @type files: C{list} of [C{float}, C{str}, callable which takes a C{str}
        argument, C{float}]
    @ivar files: Information about files to be monitored.  Each list entry
        provides the following information for a file: interval in seconds
        between checks, filename, callback function, time of last modification
        to the file.

    @type intervals: L{_IntervalDifferentialIterator}
    @ivar intervals: Intervals between successive file checks.

    @type _call: L{IDelayedCall}
    @ivar _call: The next scheduled call to check a file.

    @type index: C{int}
    @ivar index: The index of the next file to be check.
    """

    def __init__(self):
        """
        Initialize the file monitoring service.
        """
        self.files = []
        self.intervals = iter(util.IntervalDifferential([], 60))


    def startService(self):
        """
        Start the file monitoring service.
        """
        service.Service.startService(self)
        self._setupMonitor()


    def _setupMonitor(self):
        """
        Schedule the next monitoring call.
        """
        from twisted.internet import reactor
        t, self.index = self.intervals.next()
        self._call = reactor.callLater(t, self._monitor)


    def stopService(self):
        """
        Stop the file monitoring service.
        """
        service.Service.stopService(self)
        if self._call:
            self._call.cancel()
            self._call = None


    def monitorFile(self, name, callback, interval=10):
        """
        Start monitoring a file for changes.

        @type name: C{str}
        @param name: The name of a file to monitor.

        @type callback: C{Callable which takes a C{str} argument}
        @param callback: The function to call when the file has changed.

        @type interval: C{float}
        @param interval: (optional) The interval in seconds between checks.
        """
        try:
            mtime = os.path.getmtime(name)
        except:
            mtime = 0
        self.files.append([interval, name, callback, mtime])
        self.intervals.addInterval(interval)


    def unmonitorFile(self, name):
        """
        Stop monitoring a file.

        @type name: C{str}
        @param name: A file name.
        """
        for i in range(len(self.files)):
            if name == self.files[i][1]:
                self.intervals.removeInterval(self.files[i][0])
                del self.files[i]
                break


    def _monitor(self):
        """
        Monitor a file and make a callback if it has changed.
        """
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
