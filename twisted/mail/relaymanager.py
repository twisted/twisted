# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Infrastructure for relaying mail through smart host

Today, internet e-mail has stopped being Peer-to-peer for many problems,
spam (unsolicited bulk mail) among them. Instead, most nodes on the
internet send all e-mail to a single computer, usually the ISP's though
sometimes other schemes, such as SMTP-after-POP, are used. This computer
is supposedly permanently up and traceable, and will do the work of
figuring out MXs and connecting to them. This kind of configuration
is usually termed "smart host", since the host we are connecting to
is "smart" (and will find MXs and connect to them) rather then just
accepting mail for a small set of domains.

The classes here are meant to facilitate support for such a configuration
for the twisted.mail SMTP server
"""

import rfc822
import os
import time

try:
    import cPickle as pickle
except ImportError:
    import pickle

from twisted.python import log
from twisted.python.failure import Failure
from twisted.python.compat import set
from twisted.mail import relay
from twisted.mail import bounce
from twisted.internet import protocol
from twisted.internet.defer import Deferred, DeferredList
from twisted.internet.error import DNSLookupError
from twisted.mail import smtp
from twisted.application import internet

class ManagedRelayerMixin:
    """SMTP Relayer which notifies a manager

    Notify the manager about successful mail, failed mail
    and broken connections
    """

    def __init__(self, manager):
        self.manager = manager

    def sentMail(self, code, resp, numOk, addresses, log):
        """called when e-mail has been sent

        we will always get 0 or 1 addresses.
        """
        message = self.names[0]
        if code in smtp.SUCCESS:
            self.manager.notifySuccess(self.factory, message)
        else:
            self.manager.notifyFailure(self.factory, message)
        del self.messages[0]
        del self.names[0]

    def connectionLost(self, reason):
        """called when connection is broken

        notify manager we will try to send no more e-mail
        """
        self.manager.notifyDone(self.factory)

class SMTPManagedRelayer(ManagedRelayerMixin, relay.SMTPRelayer):
    def __init__(self, messages, manager, *args, **kw):
        """
        @type messages: C{list} of C{str}
        @param messages: Filenames of messages to relay

        manager should support .notifySuccess, .notifyFailure
        and .notifyDone
        """
        ManagedRelayerMixin.__init__(self, manager)
        relay.SMTPRelayer.__init__(self, messages, *args, **kw)

class ESMTPManagedRelayer(ManagedRelayerMixin, relay.ESMTPRelayer):
    def __init__(self, messages, manager, *args, **kw):
        """
        @type messages: C{list} of C{str}
        @param messages: Filenames of messages to relay

        manager should support .notifySuccess, .notifyFailure
        and .notifyDone
        """
        ManagedRelayerMixin.__init__(self, manager)
        relay.ESMTPRelayer.__init__(self, messages, *args, **kw)

class SMTPManagedRelayerFactory(protocol.ClientFactory):
    protocol = SMTPManagedRelayer

    def __init__(self, messages, manager, *args, **kw):
        self.messages = messages
        self.manager = manager
        self.pArgs = args
        self.pKwArgs = kw

    def buildProtocol(self, addr):
        protocol = self.protocol(self.messages, self.manager, *self.pArgs,
            **self.pKwArgs)
        protocol.factory = self
        return protocol

    def clientConnectionFailed(self, connector, reason):
        """called when connection could not be made

        our manager should be notified that this happened,
        it might prefer some other host in that case"""
        self.manager.notifyNoConnection(self)
        self.manager.notifyDone(self)

class ESMTPManagedRelayerFactory(SMTPManagedRelayerFactory):
    protocol = ESMTPManagedRelayer

    def __init__(self, messages, manager, secret, contextFactory, *args, **kw):
        self.secret = secret
        self.contextFactory = contextFactory
        SMTPManagedRelayerFactory.__init__(self, messages, manager, *args, **kw)

    def buildProtocol(self, addr):
        s = self.secret and self.secret(addr)
        protocol = self.protocol(self.messages, self.manager, s,
            self.contextFactory, *self.pArgs, **self.pKwArgs)
        protocol.factory = self
        return protocol

class Queue:
    """A queue of ougoing emails."""

    noisy = True

    def __init__(self, directory):
        self.directory = directory
        self._init()

    def _init(self):
        self.n = 0
        self.waiting = {}
        self.relayed = {}
        self.readDirectory()

    def __getstate__(self):
        """(internal) delete volatile state"""
        return {'directory' : self.directory}

    def __setstate__(self, state):
        """(internal) restore volatile state"""
        self.__dict__.update(state)
        self._init()

    def readDirectory(self):
        """Read the messages directory.

        look for new messages.
        """
        for message in os.listdir(self.directory):
            # Skip non data files
            if message[-2:]!='-D':
                continue
            self.addMessage(message[:-2])

    def getWaiting(self):
        return self.waiting.keys()

    def hasWaiting(self):
        return len(self.waiting) > 0

    def getRelayed(self):
        return self.relayed.keys()

    def setRelaying(self, message):
        del self.waiting[message]
        self.relayed[message] = 1

    def setWaiting(self, message):
        del self.relayed[message]
        self.waiting[message] = 1

    def addMessage(self, message):
        if message not in self.relayed:
            self.waiting[message] = 1
            if self.noisy:
                log.msg('Set ' + message + ' waiting')

    def done(self, message):
        """Remove message to from queue."""
        message = os.path.basename(message)
        os.remove(self.getPath(message) + '-D')
        os.remove(self.getPath(message) + '-H')
        del self.relayed[message]

    def getPath(self, message):
        """Get the path in the filesystem of a message."""
        return os.path.join(self.directory, message)

    def getEnvelope(self, message):
        return pickle.load(self.getEnvelopeFile(message))

    def getEnvelopeFile(self, message):
        return open(os.path.join(self.directory, message+'-H'), 'rb')

    def createNewMessage(self):
        """Create a new message in the queue.

        Return a tuple - file-like object for headers, and ISMTPMessage.
        """
        fname = "%s_%s_%s_%s" % (os.getpid(), time.time(), self.n, id(self))
        self.n = self.n + 1
        headerFile = open(os.path.join(self.directory, fname+'-H'), 'wb')
        tempFilename = os.path.join(self.directory, fname+'-C')
        finalFilename = os.path.join(self.directory, fname+'-D')
        messageFile = open(tempFilename, 'wb')

        from twisted.mail.mail import FileMessage
        return headerFile,FileMessage(messageFile, tempFilename, finalFilename)


class _AttemptManager(object):
    """
    Manage the state of a single attempt to flush the relay queue.
    """
    def __init__(self, manager):
        self.manager = manager
        self._completionDeferreds = []


    def getCompletionDeferred(self):
        self._completionDeferreds.append(Deferred())
        return self._completionDeferreds[-1]


    def _finish(self, relay, message):
        self.manager.managed[relay].remove(os.path.basename(message))
        self.manager.queue.done(message)


    def notifySuccess(self, relay, message):
        """a relay sent a message successfully

        Mark it as sent in our lists
        """
        if self.manager.queue.noisy:
            log.msg("success sending %s, removing from queue" % message)
        self._finish(relay, message)


    def notifyFailure(self, relay, message):
        """Relaying the message has failed."""
        if self.manager.queue.noisy:
            log.msg("could not relay "+message)
        # Moshe - Bounce E-mail here
        # Be careful: if it's a bounced bounce, silently
        # discard it
        message = os.path.basename(message)
        fp = self.manager.queue.getEnvelopeFile(message)
        from_, to = pickle.load(fp)
        fp.close()
        from_, to, bounceMessage = bounce.generateBounce(open(self.manager.queue.getPath(message)+'-D'), from_, to)
        fp, outgoingMessage = self.manager.queue.createNewMessage()
        pickle.dump([from_, to], fp)
        fp.close()
        for line in bounceMessage.splitlines():
             outgoingMessage.lineReceived(line)
        outgoingMessage.eomReceived()
        self._finish(relay, self.manager.queue.getPath(message))


    def notifyDone(self, relay):
        """A relaying SMTP client is disconnected.

        unmark all pending messages under this relay's responsibility
        as being relayed, and remove the relay.
        """
        for message in self.manager.managed.get(relay, ()):
            if self.manager.queue.noisy:
                log.msg("Setting " + message + " waiting")
            self.manager.queue.setWaiting(message)
        try:
            del self.manager.managed[relay]
        except KeyError:
            pass
        notifications = self._completionDeferreds
        self._completionDeferreds = None
        for d in notifications:
            d.callback(None)


    def notifyNoConnection(self, relay):
        """Relaying SMTP client couldn't connect.

        Useful because it tells us our upstream server is unavailable.
        """
        # Back off a bit
        try:
            msgs = self.manager.managed[relay]
        except KeyError:
            log.msg("notifyNoConnection passed unknown relay!")
            return

        if self.manager.queue.noisy:
            log.msg("Backing off on delivery of " + str(msgs))
        def setWaiting(queue, messages):
            map(queue.setWaiting, messages)
        from twisted.internet import reactor
        reactor.callLater(30, setWaiting, self.manager.queue, msgs)
        del self.manager.managed[relay]



class SmartHostSMTPRelayingManager:
    """Manage SMTP Relayers

    Manage SMTP relayers, keeping track of the existing connections,
    each connection's responsibility in term of messages. Create
    more relayers if the need arises.

    Someone should press .checkState periodically

    @ivar fArgs: Additional positional arguments used to instantiate
    C{factory}.

    @ivar fKwArgs: Additional keyword arguments used to instantiate
    C{factory}.

    @ivar factory: A callable which returns a ClientFactory suitable for
    making SMTP connections.
    """

    factory = SMTPManagedRelayerFactory

    PORT = 25

    mxcalc = None

    def __init__(self, queue, maxConnections=2, maxMessagesPerConnection=10):
        """
        @type queue: Any implementor of C{IQueue}
        @param queue: The object used to queue messages on their way to
        delivery.

        @type maxConnections: C{int}
        @param maxConnections: The maximum number of SMTP connections to
        allow to be opened at any given time.

        @type maxMessagesPerConnection: C{int}
        @param maxMessagesPerConnection: The maximum number of messages a
        relayer will be given responsibility for.

        Default values are meant for a small box with 1-5 users.
        """
        self.maxConnections = maxConnections
        self.maxMessagesPerConnection = maxMessagesPerConnection
        self.managed = {} # SMTP clients we're managing
        self.queue = queue
        self.fArgs = ()
        self.fKwArgs = {}

    def __getstate__(self):
        """(internal) delete volatile state"""
        dct = self.__dict__.copy()
        del dct['managed']
        return dct

    def __setstate__(self, state):
        """(internal) restore volatile state"""
        self.__dict__.update(state)
        self.managed = {}

    def checkState(self):
        """
        Synchronize with the state of the world, and maybe launch a new
        relay.

        Call me periodically to check I am still up to date.

        @return: None or a Deferred which fires when all of the SMTP clients
        started by this call have disconnected.
        """
        self.queue.readDirectory()
        if (len(self.managed) >= self.maxConnections):
            return
        if  not self.queue.hasWaiting():
            return

        return self._checkStateMX()

    def _checkStateMX(self):
        nextMessages = self.queue.getWaiting()
        nextMessages.reverse()

        exchanges = {}
        for msg in nextMessages:
            from_, to = self.queue.getEnvelope(msg)
            name, addr = rfc822.parseaddr(to)
            parts = addr.split('@', 1)
            if len(parts) != 2:
                log.err("Illegal message destination: " + to)
                continue
            domain = parts[1]

            self.queue.setRelaying(msg)
            exchanges.setdefault(domain, []).append(self.queue.getPath(msg))
            if len(exchanges) >= (self.maxConnections - len(self.managed)):
                break

        if self.mxcalc is None:
            self.mxcalc = MXCalculator()

        relays = []
        for (domain, msgs) in exchanges.iteritems():
            manager = _AttemptManager(self)
            factory = self.factory(msgs, manager, *self.fArgs, **self.fKwArgs)
            self.managed[factory] = map(os.path.basename, msgs)
            relayAttemptDeferred = manager.getCompletionDeferred()
            connectSetupDeferred = self.mxcalc.getMX(domain)
            connectSetupDeferred.addCallback(lambda mx: str(mx.name))
            connectSetupDeferred.addCallback(self._cbExchange, self.PORT, factory)
            connectSetupDeferred.addErrback(lambda err: (relayAttemptDeferred.errback(err), err)[1])
            connectSetupDeferred.addErrback(self._ebExchange, factory, domain)
            relays.append(relayAttemptDeferred)
        return DeferredList(relays)


    def _cbExchange(self, address, port, factory):
        from twisted.internet import reactor
        reactor.connectTCP(address, port, factory)

    def _ebExchange(self, failure, factory, domain):
        log.err('Error setting up managed relay factory for ' + domain)
        log.err(failure)
        def setWaiting(queue, messages):
            map(queue.setWaiting, messages)
        from twisted.internet import reactor
        reactor.callLater(30, setWaiting, self.queue, self.managed[factory])
        del self.managed[factory]

class SmartHostESMTPRelayingManager(SmartHostSMTPRelayingManager):
    factory = ESMTPManagedRelayerFactory

def _checkState(manager):
    manager.checkState()

def RelayStateHelper(manager, delay):
    return internet.TimerService(delay, _checkState, manager)



class CanonicalNameLoop(Exception):
    """
    When trying to look up the MX record for a host, a set of CNAME records was
    found which form a cycle and resolution was abandoned.
    """


class CanonicalNameChainTooLong(Exception):
    """
    When trying to look up the MX record for a host, too many CNAME records
    which point to other CNAME records were encountered and resolution was
    abandoned.
    """


class MXCalculator:
    """
    A utility for looking up mail exchange hosts and tracking whether they are
    working or not.

    @ivar clock: L{IReactorTime} provider which will be used to decide when to
        retry mail exchanges which have not been working.
    """
    timeOutBadMX = 60 * 60 # One hour
    fallbackToDomain = True

    def __init__(self, resolver=None, clock=None):
        self.badMXs = {}
        if resolver is None:
            from twisted.names.client import createResolver
            resolver = createResolver()
        self.resolver = resolver
        if clock is None:
            from twisted.internet import reactor as clock
        self.clock = clock


    def markBad(self, mx):
        """Indicate a given mx host is not currently functioning.

        @type mx: C{str}
        @param mx: The hostname of the host which is down.
        """
        self.badMXs[str(mx)] = self.clock.seconds() + self.timeOutBadMX

    def markGood(self, mx):
        """Indicate a given mx host is back online.

        @type mx: C{str}
        @param mx: The hostname of the host which is up.
        """
        try:
            del self.badMXs[mx]
        except KeyError:
            pass

    def getMX(self, domain, maximumCanonicalChainLength=3):
        """
        Find an MX record for the given domain.

        @type domain: C{str}
        @param domain: The domain name for which to look up an MX record.

        @type maximumCanonicalChainLength: C{int}
        @param maximumCanonicalChainLength: The maximum number of unique CNAME
            records to follow while looking up the MX record.

        @return: A L{Deferred} which is called back with a string giving the
            name in the found MX record or which is errbacked if no MX record
            can be found.
        """
        mailExchangeDeferred = self.resolver.lookupMailExchange(domain)
        mailExchangeDeferred.addCallback(self._filterRecords)
        mailExchangeDeferred.addCallback(
            self._cbMX, domain, maximumCanonicalChainLength)
        mailExchangeDeferred.addErrback(self._ebMX, domain)
        return mailExchangeDeferred


    def _filterRecords(self, records):
        """
        Convert a DNS response (a three-tuple of lists of RRHeaders) into a
        mapping from record names to lists of corresponding record payloads.
        """
        recordBag = {}
        for answer in records[0]:
            recordBag.setdefault(str(answer.name), []).append(answer.payload)
        return recordBag


    def _cbMX(self, answers, domain, cnamesLeft):
        """
        Try to find the MX host from the given DNS information.

        This will attempt to resolve CNAME results.  It can recognize loops
        and will give up on non-cyclic chains after a specified number of
        lookups.
        """
        # Do this import here so that relaymanager.py doesn't depend on
        # twisted.names, only MXCalculator will.
        from twisted.names import dns, error

        seenAliases = set()
        exchanges = []
        # Examine the answers for the domain we asked about
        pertinentRecords = answers.get(domain, [])
        while pertinentRecords:
            record = pertinentRecords.pop()

            # If it's a CNAME, we'll need to do some more processing
            if record.TYPE == dns.CNAME:

                # Remember that this name was an alias.
                seenAliases.add(domain)

                canonicalName = str(record.name)
                # See if we have some local records which might be relevant.
                if canonicalName in answers:

                    # Make sure it isn't a loop contained entirely within the
                    # results we have here.
                    if canonicalName in seenAliases:
                        return Failure(CanonicalNameLoop(record))

                    pertinentRecords = answers[canonicalName]
                    exchanges = []
                else:
                    if cnamesLeft:
                        # Request more information from the server.
                        return self.getMX(canonicalName, cnamesLeft - 1)
                    else:
                        # Give up.
                        return Failure(CanonicalNameChainTooLong(record))

            # If it's an MX, collect it.
            if record.TYPE == dns.MX:
                exchanges.append((record.preference, record))

        if exchanges:
            exchanges.sort()
            for (preference, record) in exchanges:
                host = str(record.name)
                if host not in self.badMXs:
                    return record
                t = self.clock.seconds() - self.badMXs[host]
                if t >= 0:
                    del self.badMXs[host]
                    return record
            return exchanges[0][1]
        else:
            # Treat no answers the same as an error - jump to the errback to try
            # to look up an A record.  This provides behavior described as a
            # special case in RFC 974 in the section headed I{Interpreting the
            # List of MX RRs}.
            return Failure(
                error.DNSNameError("No MX records for %r" % (domain,)))


    def _ebMX(self, failure, domain):
        from twisted.names import error, dns

        if self.fallbackToDomain:
            failure.trap(error.DNSNameError)
            log.msg("MX lookup failed; attempting to use hostname (%s) directly" % (domain,))

            # Alright, I admit, this is a bit icky.
            d = self.resolver.getHostByName(domain)
            def cbResolved(addr):
                return dns.Record_MX(name=addr)
            def ebResolved(err):
                err.trap(error.DNSNameError)
                raise DNSLookupError()
            d.addCallbacks(cbResolved, ebResolved)
            return d
        elif failure.check(error.DNSNameError):
            raise IOError("No MX found for %r" % (domain,))
        return failure
