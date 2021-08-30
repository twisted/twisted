# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny demo_scroll.tac
#
# Re-using a private key is dangerous, generate one.
#
# For this example you can use:
#
# $ ckeygen -t rsa -f ssh-keys/ssh_host_rsa_key

"""
Simple echo-ish server that uses the scroll-region.

This demo sets up two listening ports: one on 6022 which accepts ssh
connections; one on 6023 which accepts telnet connections.  No login
for the telnet server is required; for the ssh server, \"username\" is
the username and \"password\" is the password.

The TerminalProtocol subclass defined here sets up a scroll-region occupying
most of the screen.  It positions the cursor at the bottom of the screen and
then echos back printable input.  When return is received, the line is
copied to the upper area of the screen (scrolling anything older up) and
clears the input line.
"""

import string

from twisted.application import internet, service
from twisted.conch.insults import insults
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm
from twisted.conch.ssh import keys
from twisted.conch.telnet import TelnetBootstrapProtocol, TelnetTransport
from twisted.cred import checkers, portal
from twisted.internet import protocol
from twisted.python import log


class DemoProtocol(insults.TerminalProtocol):
    """Copies input to an upwards scrolling region."""

    width = 80
    height = 24

    def connectionMade(self):
        self.buffer = []
        self.terminalSize(self.width, self.height)

    # ITerminalListener
    def terminalSize(self, width, height):
        self.width = width
        self.height = height

        self.terminal.setScrollRegion(0, height - 1)
        self.terminal.cursorPosition(0, height)
        self.terminal.write("> ")

    def unhandledControlSequence(self, seq):
        log.msg(f"Client sent something weird: {seq!r}")

    def keystrokeReceived(self, keyID, modifier):
        if keyID == "\r":
            self.terminal.cursorPosition(0, self.height - 2)
            self.terminal.nextLine()
            self.terminal.write("".join(self.buffer))
            self.terminal.cursorPosition(0, self.height - 1)
            self.terminal.eraseToLineEnd()
            self.terminal.write("> ")
            self.buffer = []
        elif keyID in list(string.printable):
            self.terminal.write(keyID)
            self.buffer.append(keyID)


def makeService(args):
    checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(username=b"password")

    f = protocol.ServerFactory()
    f.protocol = lambda: TelnetTransport(
        TelnetBootstrapProtocol,
        insults.ServerProtocol,
        args["protocolFactory"],
        *args.get("protocolArgs", ()),
        **args.get("protocolKwArgs", {}),
    )
    tsvc = internet.TCPServer(args["telnet"], f)

    def chainProtocolFactory():
        return insults.ServerProtocol(
            args["protocolFactory"],
            *args.get("protocolArgs", ()),
            **args.get("protocolKwArgs", {}),
        )

    rlm = TerminalRealm()
    rlm.chainedProtocolFactory = chainProtocolFactory
    ptl = portal.Portal(rlm, [checker])
    f = ConchFactory(ptl)
    f.publicKeys[b"ssh-rsa"] = keys.Key.fromFile("ssh-keys/ssh_host_rsa_key.pub")
    f.privateKeys[b"ssh-rsa"] = keys.Key.fromFile("ssh-keys/ssh_host_rsa_key")
    csvc = internet.TCPServer(args["ssh"], f)

    m = service.MultiService()
    tsvc.setServiceParent(m)
    csvc.setServiceParent(m)
    return m


application = service.Application("Scroll Region Demo App")

makeService(
    {"protocolFactory": DemoProtocol, "telnet": 6023, "ssh": 6022}
).setServiceParent(application)
