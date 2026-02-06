#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

from zope.interface import implementer

from twisted.conch import avatar
from twisted.conch.checkers import InMemorySSHKeyDB, SSHPublicKeyChecker
from twisted.conch.ssh import connection, factory, keys, session, userauth
from twisted.conch.ssh.transport import SSHServerTransport
from twisted.cred import portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.internet import protocol, reactor
from twisted.python import components, log

log.startLogging(sys.stderr)

"""
Example of running a custom protocol as a shell session over an SSH channel.

Warning! This implementation is here to help you understand how Conch SSH
server works. You should not use this code in production.

Re-using a private key is dangerous, generate one.

For this example you can use:

$ ckeygen -t rsa -f ssh-keys/ssh_host_rsa_key
$ ckeygen -t rsa -f ssh-keys/client_rsa

Re-using DH primes and having such a short primes list is dangerous, generate
your own primes.

In this example the implemented SSH server identifies itself using an RSA host
key and authenticates clients using username "user" and password "password" or
using a SSH RSA key.

# Clean the previous server key as we should now have a new one
$ ssh-keygen -f ~/.ssh/known_hosts -R [localhost]:5022
# Connect with password
$ ssh -p 5022 -i ssh-keys/client_rsa user@localhost
# Connect with the SSH client key.
$ ssh -p 5022 -i ssh-keys/client_rsa user@localhost
"""

# Path to RSA SSH keys used by the server.
SERVER_RSA_PRIVATE = "ssh-keys/ssh_host_rsa_key"
SERVER_RSA_PUBLIC = "ssh-keys/ssh_host_rsa_key.pub"

# Path to RSA SSH keys accepted by the server.
CLIENT_RSA_PUBLIC = "ssh-keys/client_rsa.pub"


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
#
# twisted.conch.openssh_compat.primes.parseModuliFile provides a parser for
# reading OpenSSH moduli file.
#
# Warning! Don't use these numbers in production.
# Generate your own data.
# Avoid 1024 bit primes https://weakdh.org
#
PRIMES = {
    2048: [
        (
            2,
            int(
                "2426544657763384657581346888965894474823693600310397077868393"
                "3705240497295505367703330163384138799145013634794444597785054"
                "5748125479903006919561762337599059762229781976243372717454710"
                "2176446353691318838172478973705741394375893696394548769093992"
                "1001501857793275011598975080236860899147312097967655185795176"
                "0369411418341859232907692585123432987448282165305950904719704"
                "0150626897691190726414391069716616579597245962241027489028899"
                "9065530463691697692913935201628660686422182978481412651196163"
                "9303832327425472811802778094751292202887555413353357988371733"
                "1585493104019994344528544370824063974340739661083982041893657"
                "4217939"
            ),
        )
    ],
    4096: [
        (
            2,
            int(
                "8896338360072960666956554817320692705506152988585223623564629"
                "6621399423965037053201590845758609032962858914980344684974286"
                "2797136176274424808060302038380613106889959709419621954145635"
                "9745645498927756607640582597997083132103281857166287942205359"
                "2801914659358387079970048537106776322156933128608032240964629"
                "7706526831155237865417316423347898948704639476720848300063714"
                "8566690545913773564541481658565082079196378755098613844498856"
                "5501586550793900950277896827387976696265031832817503062386128"
                "5062331536562421699321671967257712201155508206384317725827233"
                "6142027687719225475523981798875719894413538627861634212487092"
                "7314303979577604977153889447845420392409945079600993777225912"
                "5621285287516787494652132525370682385152735699722849980820612"
                "3709076387834615230428138807577711774231925592999456202847308"
                "3393989687120016431260548916578950183006118751773893012324287"
                "3304901483476323853308396428713114053429620808491032573674192"
                "3854889258666071928702496194370274594569914312983133822049809"
                "8897129264121785413015683094180147494066773606688103698028652"
                "0892090232096545650051755799297658390763820738295370567143697"
                "6176702912637347103928738239565891710671678397388962498919556"
                "8943711148674858788771888256438487058313550933969509621845117"
                "4112035938859"
            ),
        )
    ],
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
        self.channelLookup.update({b"session": session.SSHSession})


@implementer(portal.IRealm)
class ExampleRealm:
    """
    When using Twisted Cred, the pluggable authentication framework, the
    C{requestAvatar} method should return a L{avatar.ConchUser} instance
    as required by the Conch SSH server.
    """

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
        if data == b"\r":
            data = b"\r\n"
        elif data == b"\x03":  # ^C
            self.transport.loseConnection()
            return
        self.transport.write(data)


@implementer(session.ISession, session.ISessionSetEnv)
class ExampleSession:
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

    def getPty(self, term, windowSize, attrs):
        """
        We don't support pseudo-terminal sessions.
        """

    def setEnv(self, name, value):
        """
        We don't support setting environment variables.
        """

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


components.registerAdapter(
    ExampleSession, ExampleAvatar, session.ISession, session.ISessionSetEnv
)


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
    # Service handlers.
    services = {
        b"ssh-userauth": userauth.SSHUserAuthServer,
        b"ssh-connection": connection.SSHConnection,
    }

    def __init__(self):
        passwdDB = InMemoryUsernamePasswordDatabaseDontUse(user="password")
        sshDB = SSHPublicKeyChecker(
            InMemorySSHKeyDB({b"user": [keys.Key.fromFile(CLIENT_RSA_PUBLIC)]})
        )
        self.portal = portal.Portal(ExampleRealm(), [passwdDB, sshDB])

    # Server's host keys.
    # To simplify the example this server is defined only with a host key of
    # type RSA.

    def getPublicKeys(self):
        """
        See: L{factory.SSHFactory}
        """
        return {b"ssh-rsa": keys.Key.fromFile(SERVER_RSA_PUBLIC)}

    def getPrivateKeys(self):
        """
        See: L{factory.SSHFactory}
        """
        return {b"ssh-rsa": keys.Key.fromFile(SERVER_RSA_PRIVATE)}

    def getPrimes(self):
        """
        See: L{factory.SSHFactory}
        """
        return PRIMES


if __name__ == "__main__":
    reactor.listenTCP(5022, ExampleFactory())
    reactor.run()
