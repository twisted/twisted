from twisted.conch.ssh import transport, userauth, connection, common, keys
from twisted.internet import defer, protocol, reactor
from twisted.python import log
import struct, sys, getpass, os

USER = 'z3p'  # replace this with a valid username
HOST = 'twistedmatrix.com' # and a valid host

class SimpleTransport(transport.SSHClientTransport):
    def verifyHostKey(self, hostKey, fingerprint):
        print 'host key fingerprint: %s' % fingerprint
        return 1

    def connectionSecure(self):
        self.requestService(
            SimpleUserAuth(USER,
                SimpleConnection()))

class SimpleUserAuth(userauth.SSHUserAuthClient):
    def getPassword(self):
        return defer.succeed(getpass.getpass("%s@%s's password: " % (USER, HOST)))

    def getPublicKey(self):
        path = os.path.expanduser('~/.ssh/id_dsa.pub') 
        # this works with rsa too
        # just change the name here and in getPrivateKey
        if not os.path.exists(path) or hasattr(self, 'lastPublicKey'):
            # the file doesn't exist, or we've tried a public key
            return
        return keys.getPublicKeyString(path)

    def getPrivateKey(self):
        path = os.path.expanduser('~/.ssh/id_dsa')
        return keys.getPrivateKeyObject(path)

class SimpleConnection(connection.SSHConnection):
    def serviceStarted(self):
        self.openChannel(TrueChannel(2**16, 2**15, self))
        self.openChannel(FalseChannel(2**16, 2**15, self))
        self.openChannel(EchoChannel(2**16, 2**15, self))

class TrueChannel(connection.SSHChannel):
    name = 'session' # needed for commands

    def openFailed(self, reason):
        print 'true failed', reason
    
    def channelOpen(self, ignoredData):
        self.conn.sendRequest(self, 'exec', common.NS('true'))

    def request_exit_status(self, data):
        status = struct.unpack('>L', data)[0]
        print 'true status was: %s' % status
        self.loseConnection()

class FalseChannel(connection.SSHChannel):
    name = 'session'

    def openFailed(self, reason):
        print 'false failed', reason

    def channelOpen(self, ignoredData):
        self.conn.sendRequest(self, 'exec', common.NS('false'))

    def request_exit_status(self, data):
        status = struct.unpack('>L', data)[0]
        print 'false status was: %s' % status
        self.loseConnection()

class EchoChannel(connection.SSHChannel):
    name = 'session'

    def openFailed(self, reason):
        print 'false failed', reason

    def channelOpen(self, ignoredData):
        self.conn.sendRequest(self, 'exec', common.NS('echo hello conch'))
        self.data = ''

    def dataReceived(self, data):
        self.data += data

    def closed(self):
        print 'got data from echo: %s' % repr(self.data)
        self.loseConnection()
        reactor.stop()

protocol.ClientCreator(reactor, SimpleTransport).connectTCP(HOST, 22)
reactor.run()
