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
import os

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
        message = self.messages[0][0]
        relay.SMTPRelayer.sentMail(self, addresses)
	if addresses: 
	    self.manager.notifySuccess(self, message)
	if addresses: 
	    self.manager.notifyFailure(self, message)

    def connectionLost(self):
        '''called when connection is broken

        notify manager we will try to send no more e-mail
        '''
        self.manager.notifyDone(self)


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
	self.relayingMessages = {}
	self.readDirectory()

    def notifySuccess(self, relay, message):
        '''a relay sent a message successfully

        Mark it as sent in our lists
        '''
        message = os.path.basename(message)
	self.managed[relay].remove(message)
	self.messages[message] = 1
	del self.relayingMessages[message]

    def notifyFailure(self, relay, message):
        log.msg("could not relay "+message)
        self.notifySuccess(relay, message)

    def notifyDone(self, relay):
        '''a relay finished

        mark all pending messages under this relay's resposibility
        as failed, and note that this relay is no longer active
        '''
        for message in self.managed[relay]:
	    self.notifyFailure(relay, message)
        del self.managed[relay]

    def __getstate__(self):
        '''(internal) delete volatile state'''
        dct = self.__dict__.copy()
	del dct['managed'], dct['relayingMessages'], dct['messages']
	return dct

    def __setstate__(self, state):
        '''(internal) restore volatile state'''
        self.__dict__.update(state)
	self.relayingMessages = {}
	self.managed = {}
	self.readDirectory()

    def readDirectory(self):
        '''read the messages directory

        look for new messages
        ''' 
	self.messages = {}
	for message in os.listdir(self.directory):
	    if not self.relayingMessages.has_key(message):
	        self.messages[message] = 1

    def checkState(self):
        '''call me periodically to check I am still up to date

        synchronize with the state of the world, and maybe launch
        a new relay
        '''
	self.readDirectory() 
	if not self.messages:
	    return
        if len(self.managed) >= self.maxConnections:
	    return
	nextMessages = self.messages.keys()[:self.maxMessagesPerConnection]
        toRelay = []
	for message in nextMessages:
	    self.relayingMessages[message] = 1
	    del self.messages[message]
	    toRelay.append(os.path.join(self.directory, message))
        protocol = SMTPManagedRelayer(toRelay, self)
	self.managed[protocol] = nextMessages
	transport = tcp.Client(self.smartHostAddr[0], int(self.smartHostAddr[1]), 
                               protocol)


# It's difficult to pickle methods
# So just have a function call the method
def checkState(manager):
    '''cause a manager to check the state'''
    manager.checkState()

def attachManagerToDelayed(manager, delayed, time=60):
    '''attach a a manager to a Delayed

    manager should be an SMTPRelayManager, delayed should be a 
    twisted.python.Delayed and time should be an integer in second,
    specifying time between checking the state
    '''
    loop = delay.Looping(time, checkState, delayed)
    loop.delayed._later(loop.loop,loop.ticks,(manager,))
