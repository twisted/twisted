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
from twisted.python import delay, log, failure
from twisted.mail import relay, mail, bounce
from twisted.internet import reactor, protocol
import os, string, time, cPickle

class SMTPManagedRelayerFactory(protocol.ClientFactory):

    def __init__(self, messages, manager):
        self.messages = messages
        self.manager = manager

    def buildProtocol(self, connection):
        protocol = SMTPManagedRelayer(self.messages, self.manager)
        protocol.factory = self
        return protocol

    def clientConnectionFailed(self, connector, reason):
        """called when connection could not be made

        our manager should be notified that this happened,
        it might prefer some other host in that case"""
        self.manager.notifyNoConection(self)
        self.manager.notifyDone(self)



class SMTPManagedRelayer(relay.SMTPRelayer):
    """SMTP Relayer which notifies a manager

    Notify the manager about successful main, failed mail
    and broken connections
    """

    identity = 'foo.bar'

    def __init__(self, messages, manager):
        """initialize with list of messages and a manager

        messages should be file names.
        manager should support .notifySuccess, .notifyFailure
        and .notifyDone
        """
        relay.SMTPRelayer.__init__(self, messages)
        self.manager = manager

    #def lineReceived(self, line):
    #    log.msg("managed -- got %s" % line)
    #    relay.SMTPRelayer.lineReceived(self, line)

    def sentMail(self, addresses):
        """called when e-mail has been sent

        we will always get 0 or 1 addresses.
        """
        message = self.names[0]
        if addresses: 
            self.manager.notifySuccess(self.factory, message)
        else: 
            self.manager.notifyFailure(self.factory, message)
        del self.messages[0]
        del self.names[0]

    def connectionLost(self):
        """called when connection is broken

        notify manager we will try to send no more e-mail
        """
        self.manager.notifyDone(self.factory)


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
        return self.waiting

    def getRelayed(self):
        return self.relayed.keys()

    def relaying(self, message):
        del self.waiting[message]
        self.relayed[message] = 1

    def waiting(self, message):
        del self.relayed[message]
        self.waiting[message] = 1

    def addMessage(self, message):
        if not self.relayed.has_key(message):
            self.waiting[message] = 1

    def done(self, message):
        """Remove message to from queue."""
        os.remove(message+'-D')
        os.remove(message+'-H')
        message = os.path.basename(message)
        del self.relayed[message]

    def getPath(self, message):
        """Get the path in the filesystem of a message."""
        return os.path.join(self.directory, message)

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
        return headerFile, mail.FileMessage(messageFile, tempFilename, finalFilename)


class SmartHostSMTPRelayingManager:
    """Manage SMTP Relayers

    Manage SMTP relayers, keeping track of the existing connections,
    each connection's responsibility in term of messages. Create
    more relayers if the need arises.

    Someone should press .checkState periodically
    """

    def __init__(self, queue, smartHostAddr, maxConnections=1, 
                 maxMessagesPerConnection=10):
        """initialize

        directory should be a directory full of pickles
        smartHostIP is the IP for the smart host
        maxConnections is the number of simultaneous relayers
        maxMessagesPerConnection is the maximum number of messages
        a relayer will be given responsibility for.

        Default values are meant for a small box with 1-5 users.
        """
        self.maxConnections = maxConnections
        self.maxMessagesPerConnection = maxMessagesPerConnection
        self.smartHostAddr = smartHostAddr
        self.managed = {} # SMTP clients we're managing
        self.queue = queue

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
        from_, to = cPickle.load(fp)
        fp.close()
	from_, to, bounceMessage = bounce.generateBounce(open(self.queue.getPath(message)+'-D'), from_, to)
        fp, outgoingMessage = self.queue.createNewMessage()
        cPickle.dump([from_, to], fp)
        fp.close()
        for line in string.split(bounceMessage, '\n')[:-1]:
             outgoingMessage.lineReceived(line)
        outgoingMessage.eomReceived()
        self._finish(relay, message)

    def notifyDone(self, relay):
        """A relaying SMTP client is disconnected.

        unmark all pending messages under this relay's resposibility
        as being relayed, and remove the relay.
        """
        for message in self.managed[relay]:
            self.queue.waiting[message] = 1
        del self.managed[relay]

    def notifyNoConnection(self, relay):
        """Relaying SMTP client couldn't connect.

        Useful because it tells us our upstream server is unavailable.
        """
        pass

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
        if (len(self.managed) >= self.maxConnections or 
            not self.queue.hasWaiting()):
            return
        nextMessages = self.queue.getWaiting()
        nextMessages = nextMessages[:self.maxMessagesPerConnection]
        toRelay = []
        for message in nextMessages:
            toRelay.append(self.queue.getPath(message))
            self.queue.relaying(message)
        factory = SMTPManagedRelayerFactory(toRelay, self)
        self.managed[factory] = nextMessages
        reactor.connectTCP(self.smartHostAddr[0], self.smartHostAddr[1],
                           factory)


class MXCalculator:

    timeOutBadMX = 60*60 # One hour

    def __init__(self):
        self.badMXs = {}

    def markBad(self, mx):
        self.badMXs[mx] = time.time()+self.timeOutBadMX

    def markGood(self, mx):
        del self.badMXs[mx]

    def getMX(self, deferred, domain):
        "TBD"

    def getMXAnswer(self, deferred, answers):
        if not answers:
            deferred.errback(failure.Failure(IOError("No MX found")))
        for answer in answers:
            if not self.badMXs.has_key(answer):
                deferred.callback(answer)
                return
            t = time.time() - self.badMXs[answer]
            if t > 0:
                del self.badMXs[answer]
                deferrd.callback(answer)
                return
        deferred.callback(answers[0])
        

# It's difficult to pickle methods
# So just have a function call the method
def checkState(manager):
    """cause a manager to check the state"""
    manager.checkState()


def attachManagerToDelayed(manager, delayed, time=1):
    """attach a a manager to a Delayed

    manager should be an SMTPRelayManager, delayed should be a 
    twisted.python.Delayed and time should be an integer in second,
    specifying time between checking the state
    """
    delayed.ticktime = 1
    loop = delay.Looping(time, checkState, delayed)
    loop.delayed._later(loop.loop,loop.ticks,(manager,))
