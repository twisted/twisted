from twisted.cred import authorizer
from twisted.conch import identity, error
from twisted.conch.insults import client, colors
from twisted.conch.ssh import factory, userauth, connection, channel, session,keys
from twisted.internet import reactor, defer
from twisted.python import log
import sys
log.startLogging(sys.stderr)

class InsultsDemoClient(client.InsultsClient):
    def connectionMade(self):
        self.initScreen()
        self.clearScreen()
        self.writeStr("Hello, and welcome to Insults!")
        self.gotoXY(10,10)
        self.setAttributes(colors.FG_RED, colors.BG_BLUE)
        self.writeStr("Here is some red text on a blue background!")
        self.setAttributes(colors.CLEAR)
        self.gotoXY(0,1)
        self.writeStr("Press 'Q' to disconnect.")
        self.gotoXY(0, 5)
        self.writeStr("You pressed: ")
        self.refresh()

    def keyReceived(self, key):
        self.gotoXY(13, 5)
        self.eraseToLine()
        if ord(key) < 27:
            key = '^' + chr(ord(key) + 64)
        self.writeStr(key)
        self.refresh()
        if key.upper() == 'Q':
            self.transport.loseConnection()

class Identity(identity.ConchIdentity):
    def validatePublicKey(self, data):
        return defer.fail(error.ConchError('no public key'))

    def verifyPlainPassword(self, password):
        if password == 'password' and self.name == 'user':
            return defer.succeed('')
        return defer.fail(error.ConchError('bad password'))

class Authorizer(authorizer.Authorizer):
    def getIdentityRequest(self, name):
        return defer.succeed(Identity(name, self))

class SSHConnection(connection.SSHConnection):
    def gotGlobalRequest(self, *args):
        return 0

    def getChannel(self, channelType, windowSize, maxPacket, data):
        if channelType == 'session':
            return SSHSession(
                    remoteWindow=windowSize,
                    remoteMaxPacket = maxPacket,
                    conn = self)
        return 0

class SSHSession(channel.SSHChannel):
    def channelOpen(self, data):
        self.winSize = None
    def request_pty_req(self, data):
        term, winSize, modes = session.parseRequest_pty_req(data)
        self.term = term
        self.winSize = winSize
        return 1
    def request_shell(self, data):
        if not self.winSize:
            return 0
        self.client = InsultsDemoClient()
        self.client.setSize(self.winSize[1], self.winSize[0])
        self.dataReceived = self.client.dataReceived
        reactor.callLater(0, self.client.makeConnection, self)
        return 1

class SSHFactory(factory.SSHFactory):
    publicKeys = {
        'ssh-rsa':keys.getPublicKeyString('/etc/ssh_host_rsa_key.pub')
    }
    privateKeys = {
        'ssh-rsa':keys.getPrivateKeyObject('/etc/ssh_host_rsa_key')
    }
    services = {
        'ssh-userauth': userauth.SSHUserAuthServer,
        'ssh-connection': SSHConnection
    }
    authorizer = Authorizer()
    
reactor.listenTCP(5022, SSHFactory())
reactor.run()
