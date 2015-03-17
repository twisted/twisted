#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.cred import portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.conch import avatar
from twisted.conch.checkers import SSHPublicKeyChecker, InMemorySSHKeyDB
from twisted.conch.ssh import factory, userauth, connection, keys, session
from twisted.conch.ssh.transport import SSHServerTransport
from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.python import components
from zope.interface import implements
import sys
log.startLogging(sys.stderr)

"""
Example of running a custom protocol as a shell session over an SSH channel.

Warning! This implementation is here to help you understand how Conch SSH
server works. You should not use this code in production.

In this example the implemented SSH server identifies itself using an RSA host
key and authenticates clients using username "user" and password "password" or
using a SSH RSA key.
"""

# Used as server host key as well as the key allowed for `user` account.
# In real life you should NOT reuse keys.
publicKey = 'ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAGEArzJx8OYOnJmzf4tfBEvLi8DVPrJ3/c9k2I/Az64fxjHf9imyRJbixtQhlH9lfNjUIx+4LmrJH5QNRsFporcHDKOTwTTYLh5KmRpslkYHRivcJSkbh/C+BR3utDS555mV'
# Private part of the private key used as server's host key and as account's
# SSH key.
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

# Pre-computed big prime numbers used in Diffie-Hellman Group Exchange as
# described in RFC4419.
# This is a short list with a single prime member and only for keys of size
# 1024 and 2048.
# You would need a list for each SSH key size that you plan to support in your
# server implementation.
# You can use OpenSSH ssh-keygen to generate these numbers.
# See the MODULI GENERATION section from the ssh-keygen man pages.
# See moduli man pages to find out more about the format used by the file
# generated using ssh-keygen.
# For Conch SSH server we only need the last 3 values:
# * size
# * generator
# * modulus
#
# The format required by the Conch SSH server is:
#
# {
#   size1: [(generator1, modulus1), (generator1, modulus2)],
#   size2: [(generator4, modulus3), (generator1, modulus4)],
# }
primes = {
    1024: [(2L, 156096651313543778571595410217704559250114948553033770757855392840961183273291234883805993188033046610903022946932272851484576959192633374396690126968589997032493458342941315946790987602763346322167058862580077578954322455929446361765756279255191622023630586895206795776981175371885918231654469745514594662643L)],
    2048: [(2L, 24265446577633846575813468889658944748236936003103970778683933705240497295505367703330163384138799145013634794444597785054574812547990300691956176233759905976222978197624337271745471021764463536913188381724789737057413943758936963945487690939921001501857793275011598975080236860899147312097967655185795176036941141834185923290769258512343298744828216530595090471970401506268976911907264143910697166165795972459622410274890288999065530463691697692913935201628660686422182978481412651196163930383232742547281180277809475129220288755541335335798837173315854931040199943445285443708240639743407396610839820418936574217939L)],
    }



class ExampleAvatar(avatar.ConchUser):
    """
    The avatar is used to configure SSH services/sessions/subsystems for
    an account.

    This account will use L{session.SSHSession} to handle a channel of
    type I{session}.
    """
    def __init__(self, username):
        avatar.ConchUser.__init__(self)
        self.username = username
        self.channelLookup.update({'session':session.SSHSession})



class ExampleRealm(object):
    """
    When using Twisted Cred, the pluggable authentication framework, the
    C{requestAvatar} method should return a L{avatar.ConchUser} instance
    as required by the Conch SSH server.
    """
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        """
        See: L{portal.IRealm.requestAvatar}
        """
        return interfaces[0], ExampleAvatar(avatarId), lambda: None



class EchoProtocol(protocol.Protocol):
    """
    This is our protocol that we will run over the shell session.
    """

    def dataReceived(self, data):
        """
        Called when client send data over the shell session.

        Just echo the received data and and if Ctrl+C is received, close the
        session.
        """
        if data == '\r':
            data = '\r\n'
        elif data == '\x03': #^C
            self.transport.loseConnection()
            return
        self.transport.write(data)



class ExampleSession(object):
    """
    This selects what to do for each type of session which is requested by the
    client via the SSH channel of type I{session}.
    """

    def __init__(self, avatar):
        """
        In this example the avatar argument is not used for session selection,
        but for example you can use it to limit I{shell} or I{exec} access
        only to specific accounts.
        """
        pass

    def getPty(self, term, windowSize, attrs):
        """
        We don't support pseudo-terminal sessions.
        """
        pass

    def execCommand(self, proto, cmd):
        """
        We don't support command execution sessions.
        """
        raise Exception("not executing commands")

    def openShell(self, transport):
        """
        Use our protocol as shell session.
        """
        protocol = EchoProtocol()
        # Connect the new protocol to the transport and the transport
        # to the new protocol so they can communicate in both directions.
        protocol.makeConnection(transport)
        transport.makeConnection(session.wrapProtocol(protocol))

    def eofReceived(self):
        pass

    def closed(self):
        pass



components.registerAdapter(ExampleSession, ExampleAvatar, session.ISession)



class ExampleFactory(factory.SSHFactory):
    """
    This is the entry point of our SSH server implementation.

    The SSH transport layer is implemented by L{SSHTransport} and is the
    protocol of this factory.

    Here we configure the server's identity (host keys) and handlers for the
    SSH services:
    * L{connection.SSHConnection} handles requests for the channel multiplexing
      service.
    * L{userauth.SSHUserAuthServer} handlers requests for the user
      authentication service.
    """
    protocol = SSHServerTransport
    # Server's host keys.
    # To simplify the example this server is defined only with a host key of
    # type RSA.
    publicKeys = {
        'ssh-rsa': keys.Key.fromString(data=publicKey)
    }
    privateKeys = {
        'ssh-rsa': keys.Key.fromString(data=privateKey)
    }
    # Service handlers.
    services = {
        'ssh-userauth': userauth.SSHUserAuthServer,
        'ssh-connection': connection.SSHConnection
    }

    def getPrimes(self):
        """
        See: L{factory.SSHFactory}
        """
        return primes


portal = portal.Portal(ExampleRealm())
passwdDB = InMemoryUsernamePasswordDatabaseDontUse()
passwdDB.addUser('user', 'password')
sshDB = SSHPublicKeyChecker(InMemorySSHKeyDB(
    {'user': [keys.Key.fromString(data=publicKey)]}))
portal.registerChecker(passwdDB)
portal.registerChecker(sshDB)
ExampleFactory.portal = portal

if __name__ == '__main__':
    reactor.listenTCP(5022, ExampleFactory())
    reactor.run()
