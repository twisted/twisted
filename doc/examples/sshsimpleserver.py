#!/usr/bin/env python
from twisted.cred import portal, authorizer, checkers
from twisted.conch import identity, error
from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.conch.ssh import factory, userauth, connection, channel, keys
from twisted.internet import reactor, protocol, defer
from twisted.python import log
import sys
log.startLogging(sys.stderr)

"""Example of running another protocol over an SSH channel.
log in with username "user" and password "password".
Alternatively, put a public key in ./id_dsa.pub and the user may be
authenticated with that.
"""

class SSHAvatar:

    def __init__(self, username):
        self.username = username

class SSHRealm:
    __implements__ = portal.IRealm,

    def requestAvatar(self, avatarId, mind, *interfaces):
        return SSHAvatar(avatarId), interfaces[0], lambda x: None

class EchoProtocol(protocol.Protocol):
    """this is our example protocol that we will run over SSH
    """
    def dataReceived(self, data):
        if data == '\r':
            data = '\r\n'
        elif data == '\x03': #^C
            self.transport.loseConnection()
        self.transport.write(data)

publicKey = 'ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAGEArzJx8OYOnJmzf4tfBEvLi8DVPrJ3/c9k2I/Az64fxjHf9imyRJbixtQhlH9lfNjUIx+4LmrJH5QNRsFporcHDKOTwTTYLh5KmRpslkYHRivcJSkbh/C+BR3utDS555mV'

privateKey = """-----BEGIN RSA PRIVATE KEY-----
MIIByAIBAAJhAK8ycfDmDpyZs3+LXwRLy4vA1T6yd/3PZNiPwM+uH8Yx3/YpskSW
4sbUIZR/ZXzY1CMfuC5qyR+UDUbBaaK3Bwyjk8E02C4eSpkabJZGB0Yr3CUpG4fw
vgUd7rQ0ueeZlQIBIwJgbh+1VZfr7WftK5lu7MHtqE1S1vPWZQYE3+VUn8yJADyb
Z4fsZaCrzW9lkIqXkE3GIY+ojdhZhkO1gbG0118sIgphwSWKRxK0mvh6ERxKqIt1
xJEJO74EykXZV4oNJ8sjAjEA3J9r2ZghVhGN6V8DnQrTk24Td0E8hU8AcP0FVP+8
PQm/g/aXf2QQkQT+omdHVEJrAjEAy0pL0EBH6EVS98evDCBtQw22OZT52qXlAwZ2
gyTriKFVoqjeEjt3SZKKqXHSApP/AjBLpF99zcJJZRq2abgYlf9lv1chkrWqDHUu
DZttmYJeEfiFBBavVYIF1dOlZT0G8jMCMBc7sOSZodFnAiryP+Qg9otSBjJ3bQML
pSTqy7c3a2AScC/YyOwkDaICHnnD3XyjMwIxALRzl0tQEKMXs6hH8ToUdlLROCrP
EhQ0wahUTCk1gKA4uPD6TMTChavbh4K63OvbKg==
-----END RSA PRIVATE KEY-----"""


class InMemoryPublicKeyChecker(SSHPublicKeyDatabase):

    def checkKey(self, credentials):
        return credentials.username == 'user' and \
            keys.getPublicKeyString(publicKey) == credentials.blob

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
                    remoteMaxPacket=maxPacket,
                    conn=self)
        return 0

class SSHSession(channel.SSHChannel):
    def channelOpen(self, data): pass
    def request_pty_req(self, data):
        # ignore, but this gets send for shell requests
        return 1
    def request_shell(self, data):
        self.client = EchoProtocol()
        self.client.makeConnection(self)
        self.dataReceived = self.client.dataReceived
        return 1
    def loseConnection(self):
        self.client.connectionLost()
        channel.SSHChannel.loseConnection(self)

class SSHFactory(factory.SSHFactory):
    publicKeys = {
        'ssh-rsa': keys.getPublicKeyString(data=publicKey)
    }
    privateKeys = {
        'ssh-rsa': keys.getPrivateKeyObject(data=privateKey)
    }
    services = {
        'ssh-userauth': userauth.SSHUserAuthServer,
        'ssh-connection': SSHConnection
    }
    

portal = portal.Portal(SSHRealm())
passwdDB = checkers.InMemoryUsernamePasswordDatabaseDontUse()
passwdDB.addUser('user', 'password')
portal.registerChecker(passwdDB)
portal.registerChecker(InMemoryPublicKeyChecker())
SSHFactory.portal = portal

reactor.listenTCP(5022, SSHFactory())
reactor.run()
