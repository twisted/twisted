#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.conch.ssh import transport, userauth, connection, common, keys, channel
from twisted.internet import defer, protocol, reactor
from twisted.python import log
import struct, sys, getpass, os

USER = 'z3p'  # replace this with a valid username
HOST = 'localhost' # and a valid host

class SimpleTransport(transport.SSHClientTransport):
    def verifyHostKey(self, hostKey, fingerprint):
        print 'host key fingerprint: %s' % fingerprint
        return defer.succeed(1) 

    def connectionSecure(self):
        self.requestService(
            SimpleUserAuth(USER,
                SimpleConnection()))

class SimpleUserAuth(userauth.SSHUserAuthClient):
    def getPassword(self):
        return defer.succeed(getpass.getpass("%s@%s's password: " % (USER, HOST)))

    def getGenericAnswers(self, name, instruction, questions):
        print name
        print instruction
        answers = []
        for prompt, echo in questions:
            if echo:
                answer = raw_input(prompt)
            else:
                answer = getpass.getpass(prompt)
            answers.append(answer)
        return defer.succeed(answers)
            
    def getPublicKey(self):
        path = os.path.expanduser('~/.ssh/id_dsa') 
        # this works with rsa too
        # just change the name here and in getPrivateKey
        if not os.path.exists(path) or self.lastPublicKey:
            # the file doesn't exist, or we've tried a public key
            return
        return keys.Key.fromFile(filename=path+'.pub').blob()

    def getPrivateKey(self):
        path = os.path.expanduser('~/.ssh/id_dsa')
        return defer.succeed(keys.Key.fromFile(path).keyObject)

class SimpleConnection(connection.SSHConnection):
    def serviceStarted(self):
        self.openChannel(TrueChannel(2**16, 2**15, self))
        self.openChannel(FalseChannel(2**16, 2**15, self))
        self.openChannel(CatChannel(2**16, 2**15, self))

class TrueChannel(channel.SSHChannel):
    name = 'session' # needed for commands

    def openFailed(self, reason):
        print 'true failed', reason
    
    def channelOpen(self, ignoredData):
        self.conn.sendRequest(self, 'exec', common.NS('true'))

    def request_exit_status(self, data):
        status = struct.unpack('>L', data)[0]
        print 'true status was: %s' % status
        self.loseConnection()

class FalseChannel(channel.SSHChannel):
    name = 'session'

    def openFailed(self, reason):
        print 'false failed', reason

    def channelOpen(self, ignoredData):
        self.conn.sendRequest(self, 'exec', common.NS('false'))

    def request_exit_status(self, data):
        status = struct.unpack('>L', data)[0]
        print 'false status was: %s' % status
        self.loseConnection()

class CatChannel(channel.SSHChannel):
    name = 'session'

    def openFailed(self, reason):
        print 'echo failed', reason

    def channelOpen(self, ignoredData):
        self.data = ''
        d = self.conn.sendRequest(self, 'exec', common.NS('cat'), wantReply = 1)
        d.addCallback(self._cbRequest)

    def _cbRequest(self, ignored):
        self.write('hello conch\n')
        self.conn.sendEOF(self)

    def dataReceived(self, data):
        self.data += data

    def closed(self):
        print 'got data from cat: %s' % repr(self.data)
        self.loseConnection()
        reactor.stop()

protocol.ClientCreator(reactor, SimpleTransport).connectTCP(HOST, 22)
reactor.run()
