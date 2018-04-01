#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
from __future__ import print_function

from twisted.conch.ssh import transport, userauth, connection, common, keys, channel
from twisted.internet import defer, protocol, reactor
from twisted.python import log
import struct, sys, getpass, os

"""
Example of using a simple SSH client.

It will try to authenticate with a SSH key or ask for a password.

Re-using a private key is dangerous, generate one.
For this example you can use:

$ ckeygen -t rsa -f ssh-keys/client_rsa
"""

# Replace this with your username.
# Default username and password will match the sshsimpleserver.py
USER = b'user'
HOST = 'localhost'
PORT = 5022
SERVER_FINGERPRINT = b'55:55:66:24:6b:03:0e:f1:ec:f8:66:c3:51:df:27:4b'

# Path to RSA SSH keys accepted by the server.
CLIENT_RSA_PUBLIC = 'ssh-keys/client_rsa.pub'
# Set CLIENT_RSA_PUBLIC to empty to not use SSH key auth.
# CLIENT_RSA_PUBLIC = ''
CLIENT_RSA_PRIVATE = 'ssh-keys/client_rsa'


class SimpleTransport(transport.SSHClientTransport):
    def verifyHostKey(self, hostKey, fingerprint):
        print('Server host key fingerprint: %s' % fingerprint)
        if SERVER_FINGERPRINT == fingerprint:
            return defer.succeed(True)
        else:
            print('Bad host key. Expecting: %s' % SERVER_FINGERPRINT)
            return defer.fail(Exception('Bad server key'))

    def connectionSecure(self):
        self.requestService(
            SimpleUserAuth(USER,
                SimpleConnection()))

class SimpleUserAuth(userauth.SSHUserAuthClient):

    def getPassword(self):
        return defer.succeed(getpass.getpass("%s@%s's password: " % (USER, HOST)))

    def getGenericAnswers(self, name, instruction, questions):
        print(name)
        print(instruction)
        answers = []
        for prompt, echo in questions:
            if echo:
                answer = raw_input(prompt)
            else:
                answer = getpass.getpass(prompt)
            answers.append(answer)
        return defer.succeed(answers)


    def getPublicKey(self):
        if (
            not CLIENT_RSA_PUBLIC or
            not os.path.exists(CLIENT_RSA_PUBLIC) or
            self.lastPublicKey
                ):
            # the file doesn't exist, or we've tried a public key
            return
        return keys.Key.fromFile(filename=CLIENT_RSA_PUBLIC)


    def getPrivateKey(self):
        """
        A deferred can also be returned.
        """
        return defer.succeed(keys.Key.fromFile(CLIENT_RSA_PRIVATE))



class SimpleConnection(connection.SSHConnection):
    def serviceStarted(self):
        self.openChannel(TrueChannel(2**16, 2**15, self))
        self.openChannel(FalseChannel(2**16, 2**15, self))
        self.openChannel(CatChannel(2**16, 2**15, self))



class TrueChannel(channel.SSHChannel):
    name = b'session' # needed for commands

    def openFailed(self, reason):
        print('true failed', reason)

    def channelOpen(self, ignoredData):
        self.conn.sendRequest(self, 'exec', common.NS('true'))

    def request_exit_status(self, data):
        status = struct.unpack('>L', data)[0]
        print('true status was: %s' % status)
        self.loseConnection()

class FalseChannel(channel.SSHChannel):
    name = b'session'

    def openFailed(self, reason):
        print('false failed', reason)

    def channelOpen(self, ignoredData):
        self.conn.sendRequest(self, 'exec', common.NS('false'))

    def request_exit_status(self, data):
        status = struct.unpack('>L', data)[0]
        print('false status was: %s' % status)
        self.loseConnection()

class CatChannel(channel.SSHChannel):
    name = b'session'

    def openFailed(self, reason):
        print('echo failed', reason)

    def channelOpen(self, ignoredData):
        self.data = b''
        d = self.conn.sendRequest(self, 'exec', common.NS('cat'), wantReply = 1)
        d.addCallback(self._cbRequest)

    def _cbRequest(self, ignored):
        self.write(b'hello conch\n')
        self.conn.sendEOF(self)

    def dataReceived(self, data):
        self.data += data

    def closed(self):
        print('got data from cat: %s' % repr(self.data))
        self.loseConnection()
        reactor.stop()


log.startLogging(sys.stdout)
protocol.ClientCreator(reactor, SimpleTransport).connectTCP(HOST, PORT)
reactor.run()
