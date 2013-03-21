#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.cred import portal, checkers
from twisted.conch import avatar
from twisted.conch.checkers import SSHPublicKeyChecker
from twisted.conch.ssh import factory, userauth, connection, keys, session
from twisted.internet import reactor, protocol
from twisted.python import log
from zope.interface import implements
import base64
import sys

"""
Example of running another protocol over an SSH channel.

If you want to see the text actually echoed, make sure that the option '-T' is
passed to ssh.  If this option is not passed, you will only see the words you
typed as you type them.

This also contains an example how to build a custom public key checker.

Either log in with any public key, or with the username 'user' and password
'password'.
"""

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


class ExampleFactory(factory.SSHFactory):
    publicKeys = {
        'ssh-rsa': keys.Key.fromString(data=publicKey)
    }
    privateKeys = {
        'ssh-rsa': keys.Key.fromString(data=privateKey)
    }
    services = {
        'ssh-userauth': userauth.SSHUserAuthServer,
        'ssh-connection': connection.SSHConnection
    }



class ExampleAvatar(avatar.ConchUser):
    """
    An implementer of L{twisted.conch.interfaces.IConchUser} - gets returned
    by the realm when an avatar is requesed
    """
    def __init__(self, username):
        avatar.ConchUser.__init__(self)
        self.username = username
        self.channelLookup.update({'session': session.SSHSession})



class ExampleRealm:
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        return interfaces[0], ExampleAvatar(avatarId), lambda: None



class EchoProtocol(protocol.Protocol):
    """this is our example protocol that we will run over SSH
    """
    def dataReceived(self, data):
        if data == '\r':
            data = '\r\n'
        elif data == '\x03':  # ^C
            self.transport.loseConnection()
            return
        # repeats what you type back - if data were not written back to
        # transport, you would not be able to see anything that you type.
        self.transport.write(data)



class ExampleSession:

    def __init__(self, avatar):
        """
        We don't use it, but the adapter is passed the avatar as its first
        argument.
        """

    def getPty(self, term, windowSize, attrs):
        pass

    def execCommand(self, proto, cmd):
        raise Exception("no executing commands")

    def openShell(self, trans):
        ep = EchoProtocol()
        ep.makeConnection(trans)
        trans.makeConnection(session.wrapProtocol(ep))

    def eofReceived(self):
        pass

    def closed(self):
        pass


from twisted.python import components
components.registerAdapter(ExampleSession, ExampleAvatar, session.ISession)


def allowAnyKeyFromAnyUser(credentials):
    """
    L{SSHPublicKeyChecker} will check the public key provided in credentials
    against a list of keys provided by a function passed to its C{__init__}.

    This function is that function.  In order to permit anyone, it
    will take the key that it is provided and return that key as the only
    element in the list.  Thus the provided key will always match one in the
    iterable of keys returned by this function.

    See L{SSHPublicKeyChecker} for more information.
    """
    log.msg(
        "{name} just attempted to log in with public key:\n{key}".format(
            name=credentials.username,
            key=base64.encodestring(credentials.blob)))
    return [keys.Key.fromString(credentials.blob)]


# also allow a user to log in as user, with password 'password'
passwdDB = checkers.InMemoryUsernamePasswordDatabaseDontUse()
passwdDB.addUser('user', 'password')

portal = portal.Portal(ExampleRealm())
portal.registerChecker(passwdDB)
portal.registerChecker(SSHPublicKeyChecker(allowAnyKeyFromAnyUser))

ExampleFactory.portal = portal

if __name__ == '__main__':
    log.startLogging(sys.stderr)
    reactor.listenTCP(5022, ExampleFactory())
    reactor.run()
