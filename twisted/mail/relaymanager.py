
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

'''infrastructure for relaying mail through smart host

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
'''
from twisted.python import delay, log
from twisted.mail import relay
from twisted.internet import tcp
import os, string


class SMTPManagedRelayer(relay.SMTPRelayer):

    '''SMTP Relayer which notifies a manager

    Notify the manager about successful main, failed mail
    and broken connections
    '''

    identity = 'foo.bar'

    def __init__(self, messages, manager):
        '''initialize with list of messages and a manager

        messages should be file names.
        manager should support .notifySuccess, .notifyFailure
        and .notifyDone
        '''
        relay.SMTPRelayer.__init__(self, messages)
        self.manager = manager

    def sentMail(self, addresses):
        '''called when e-mail has been sent

        we will always get 0 or 1 addresses.
        '''
        message = self.names[0]
        relay.SMTPRelayer.sentMail(self, addresses)
        if addresses: 
            self.manager.notifySuccess(self, message)
        else: 
            self.manager.notifyFailure(self, message)

    def connectionFailed(self):
        '''called when connection could not be made

        our manager should be notified that this happened,
        it might prefer some other host in that case'''
        self.manager.notifyNoConection(self)
        self.manager.notifyDone(self)

    def connectionLost(self):
        '''called when connection is broken

        notify manager we will try to send no more e-mail
        '''
        self.manager.notifyDone(self)


class MessageCollection:

    def __init__(self):
        self.waiting = {}
        self.relayed = {}

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
        del self.relayed[message]


class SmartHostSMTPRelayingManager:

    '''Manage SMTP Relayers

    Manage SMTP relayers, keeping track of the existing connections,
    each connection's responsibility in term of messages. Create
    more relayers if the need arises.

    Someone should press .checkState periodically
    '''

    def __init__(self, directory, smartHostAddr, maxConnections=1, 
                 maxMessagesPerConnection=10):
        '''initialize

        directory should be a directory full of pickles
        smartHostIP is the IP for the smart host
        maxConnections is the number of simultaneous relayers
        maxMessagesPerConnection is the maximum number of messages
        a relayer will be given responsibility for.

        Default values are meant for a small box with 1-5 users.
        '''
        self.directory = directory
        self.maxConnections = maxConnections
        self.maxMessagesPerConnection = maxMessagesPerConnection
        self.smartHostAddr = smartHostAddr
        self.managed = {}
        self.messageCollection = MessageCollection()
        self.readDirectory()

    def _finish(self, message):
        os.remove(message+'-D')
        os.remove(message+'-H')
        message = os.path.basename(message)
        self.messageCollection.done(message)

    def notifySuccess(self, relay, message):
        '''a relay sent a message successfully

        Mark it as sent in our lists
        '''
        self._finish(message)

    def notifyFailure(self, relay, message):
        log.msg("could not relay "+message)
        # Moshe - Bounce E-mail here
        # Be careful: if it's a bounced bounce, silently
        # discard it
        self._finish(message)

    def notifyDone(self, relay):
        '''a relay finished

        unmark all pending messages under this relay's resposibility
        as being relayed, and remove the relay.
        '''
        for message in self.managed[relay]:
            self.messageCollection.waiting(message) 
        del self.managed[relay]

    def notifyNoConnection(self, relay):
        pass

    def __getstate__(self):
        '''(internal) delete volatile state'''
        dct = self.__dict__.copy()
        del dct['managed'], dct['messageCollection']
        return dct

    def __setstate__(self, state):
        '''(internal) restore volatile state'''
        self.__dict__.update(state)
        self.messageCollection = MessageCollection()
        self.managed = {}
        self.readDirectory()

    def readDirectory(self):
        '''read the messages directory

        look for new messages
        ''' 
        for message in os.listdir(self.directory):
            # Skip non data files
            if message[-2:]!='-D':
                continue
            self.messageCollection.addMessage(message[:-2])

    def checkState(self):
        '''call me periodically to check I am still up to date

        synchronize with the state of the world, and maybe launch
        a new relay
        '''
        self.readDirectory() 
        if (len(self.managed) >= self.maxConnections or 
            not self.messageCollection.hasWaiting()):
            return
        nextMessages = self.messageCollection.getWaiting()
        nextMessages = nextMessages[:self.maxMessagesPerConnection]
        toRelay = []
        for message in nextMessages:
            toRelay.append(os.path.join(self.directory, message))
            self.messageCollection.relaying(message)
        protocol = SMTPManagedRelayer(toRelay, self)
        self.managed[protocol] = nextMessages
        transport = tcp.Client(self.smartHostAddr[0], self.smartHostAddr[1], 
                               protocol)

class MXCalculator:

    timeOutBadMX = 60*60 # One hour

    def __init__(self):
        self.badMXs = {}

    def markBad(self, mx):
        self.badMXs[mx] = time.time()+self.timeOutBadMX

    def markGood(self, mx):
        del self.badMXs[mx]

    def getMX(self, deferred, domain):
        ""
        # TBD

    def getMXAnswer(self, deferred, answers):
        if not answers:
            deferred.errback("No MX found")
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
    '''cause a manager to check the state'''
    manager.checkState()


def attachManagerToDelayed(manager, delayed, time=1):
    '''attach a a manager to a Delayed

    manager should be an SMTPRelayManager, delayed should be a 
    twisted.python.Delayed and time should be an integer in second,
    specifying time between checking the state
    '''
    loop = delay.Looping(time, checkState, delayed)
    loop.delayed._later(loop.loop,loop.ticks,(manager,))
