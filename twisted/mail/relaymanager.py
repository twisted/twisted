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

"""Infrastructure for relaying mail through smart host

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

from twisted.python import log
from twisted.python import util
from twisted.mail import relay
from twisted.mail import bounce
from twisted.internet import protocol
from twisted.protocols import smtp
from twisted.application import internet

import rfc822
import os
import time

try:
    import cPickle as pickle
except ImportError:
    import pickle

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

    def _finish(self, relay, message):
        self.managed[relay].remove(os.path.basename(message))
        self.queue.done(message)

    def notifySuccess(self, relay, message):
        """a relay sent a message successfully

        Mark it as sent in our lists
        """
        log.msg("success sending %s, removing from queue" % message)
        self._finish(relay, message)

    def notifyFailure(self, relay, message):
        """Relaying the message has failed."""
        log.msg("could not relay "+message)
        # Moshe - Bounce E-mail here
        # Be careful: if it's a bounced bounce, silently
        # discard it
        message = os.path.basename(message)
        fp = self.queue.getEnvelopeFile(message)
        from_, to = pickle.load(fp)
        fp.close()
        from_, to, bounceMessage = bounce.generateBounce(open(self.queue.getPath(message)+'-D'), from_, to)
        fp, outgoingMessage = self.queue.createNewMessage()
        pickle.dump([from_, to], fp)
        fp.close()
        for line in bounceMessage.splitlines():
             outgoingMessage.lineReceived(line)
        outgoingMessage.eomReceived()
        self._finish(relay, self.queue.getPath(message))

    def notifyDone(self, relay):
        """A relaying SMTP client is disconnected.

        unmark all pending messages under this relay's resposibility
        as being relayed, and remove the relay.
        """
        for message in self.managed.get(relay, ()):
            log.msg("Setting " + message + " waiting")
            self.queue.setWaiting(message)
        try:
            del self.managed[relay]
        except KeyError:
            pass

    def notifyNoConnection(self, relay):
        """Relaying SMTP client couldn't connect.

        Useful because it tells us our upstream server is unavailable.
        """
        # Back off a bit
        try:
            msgs = self.managed[relay]
        except KeyError:
            log.msg("notifyNoConnection passed unknown relay!")
            return

        log.msg("Backing off on delivery of " + str(msgs))
        def setWaiting(queue, messages):
            map(queue.setWaiting, messages)
        from twisted.internet import reactor
        reactor.callLater(30, setWaiting, self.queue, msgs)
        del self.managed[relay]

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
        """call me periodically to check I am still up to date

        synchronize with the state of the world, and maybe launch
        a new relay
        """
        self.queue.readDirectory() 
        if (len(self.managed) >= self.maxConnections):
            return
        if  not self.queue.hasWaiting():
            return

        self._checkStateMX()
    
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
        
        for (domain, msgs) in exchanges.iteritems():
            factory = self.factory(msgs, self, *self.fArgs, **self.fKwArgs)
            self.managed[factory] = map(os.path.basename, msgs)
            self.mxcalc.getMX(domain
            ).addCallback(lambda mx: str(mx.exchange),
            ).addCallback(self._cbExchange, self.PORT, factory
            ).addErrback(self._ebExchange, factory, domain
            )

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

class MXCalculator:
    timeOutBadMX = 60 * 60 # One hour
    fallbackToDomain = True

    def __init__(self, resolver = None):
        self.badMXs = {}
        if resolver is None:
            from twisted.names.client import createResolver
            resolver = createResolver()
        self.resolver = resolver

    def markBad(self, mx):
        self.badMXs[mx] = time.time() + self.timeOutBadMX

    def markGood(self, mx):
        try:
            del self.badMXs[mx]
        except KeyError:
            pass

    def getMX(self, domain):
        return self.resolver.lookupMailExchange(domain
        ).addCallback(self._filterRecords
        ).addCallback(self._cbMX, domain
        ).addErrback(self._ebMX, domain
        )

    def _filterRecords(self, records):
        answers = records[0]
        return [a.payload for a in answers]

    def _cbMX(self, answers, domain):
        if not answers:
            raise IOError("No MX found for %r" % (domain,))
        answers = util.dsu(answers, lambda e: e.preference)
        for answer in answers:
            if answer not in self.badMXs:
                return answer
            t = time.time() - self.badMXs[answer]
            if t > 0:
                del self.badMXs[answer]
                return answer
        return answer[0]

    def _ebMX(self, failure, domain):
        if self.fallbackToDomain:
            failure.trap(IOError)
            log.msg("MX lookup failed; attempting to use hostname (%s) directly" % (domain,))

            # Alright, I admit, this is a bit icky.
            from twisted.protocols import dns
            return self.resolver.getHostByName(domain
                ).addCallback(lambda h: dns.Record_MX(exchange=h)
                )
        return failure
