# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny demo_manhole.tac
#
# Re-using a private key is dangerous, generate one.
#
# For this example you can use:
#
# $ ckeygen -t rsa -f ssh-keys/ssh_host_rsa_key

"""
An interactive Python interpreter with syntax coloring.

Nothing interesting is actually defined here.  Two listening ports are
set up and attached to protocols which know how to properly set up a
ColoredManhole instance.
"""

from twisted.application import internet, service
from twisted.conch.insults import insults
from twisted.conch.manhole import ColoredManhole
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm
from twisted.conch.ssh import keys
from twisted.conch.telnet import TelnetBootstrapProtocol, TelnetTransport
from twisted.cred import checkers, portal
from twisted.internet import protocol


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


application = service.Application("Interactive Python Interpreter")

makeService(
    {
        "protocolFactory": ColoredManhole,
        "protocolArgs": (None,),
        "telnet": 6023,
        "ssh": 6022,
    }
).setServiceParent(application)
