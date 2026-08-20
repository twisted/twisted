# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny window.tac
#
# Re-using a private key is dangerous, generate one.
#
# For this example you can use:
#
# $ ckeygen -t rsa -f ssh-keys/ssh_host_rsa_key

"""
Widgets demo.

You can run this .tac file directly with:
    twistd -ny window.tac

Demonstrates various widgets or buttons, such as scrollable regions,
drawable canvas, etc.

This demo sets up two listening ports: one on 6022 which accepts ssh
connections; one on 6023 which accepts telnet connections.  No login for the
telnet server is required; for the ssh server, "username" is the username and
"password" is the password.
"""


import random
import string

from twisted.application import internet, service
from twisted.conch.insults import insults, window
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm
from twisted.conch.ssh import keys
from twisted.conch.telnet import TelnetBootstrapProtocol, TelnetTransport
from twisted.cred import checkers, portal
from twisted.internet import protocol, reactor, task
from twisted.python import log


class DrawableCanvas(window.Canvas):
    x = 0
    y = 0

    def func_LEFT_ARROW(self, modifier):
        self.x -= 1
        self.repaint()

    def func_RIGHT_ARROW(self, modifier):
        self.x += 1
        self.repaint()

    def func_UP_ARROW(self, modifier):
        self.y -= 1
        self.repaint()

    def func_DOWN_ARROW(self, modifier):
        self.y += 1
        self.repaint()

    def characterReceived(self, keyID, modifier):
        self[self.x, self.y] = keyID
        self.x += 1
        self.repaint()

    def keystrokeReceived(self, keyID, modifier):
        if keyID == b"\r" or keyID == b"\v":
            return
        window.Canvas.keystrokeReceived(self, keyID, modifier)
        if self.x >= self.width:
            self.x = 0
        elif self.x < 0:
            self.x = self.width - 1

        if self.y >= self.height:
            self.y = 0
        elif self.y < 0:
            self.y = self.height - 1
        self.repaint()

    def render(self, width, height, terminal):
        window.Canvas.render(self, width, height, terminal)
        if self.focused:
            terminal.cursorPosition(self.x, self.y)
            ch = chr(self[self.x, self.y])
            window.cursor(terminal, ch)


class ButtonDemo(insults.TerminalProtocol):
    width = 80
    height = 24

    def _draw(self):
        self.window.draw(self.width, self.height, self.terminal)

    def _redraw(self):
        self.window.filthy()
        self._draw()

    def _schedule(self, f):
        reactor.callLater(0, f)

    def connectionMade(self):
        self.terminal.eraseDisplay()
        self.terminal.resetPrivateModes([insults.privateModes.CURSOR_MODE])

        self.window = window.TopWindow(self._draw, self._schedule)
        self.output = window.TextOutput((15, 1))
        self.input = window.TextInput(15, self._setText)
        selections = [num.encode("utf-8") for num in map(str, range(100))]
        self.select1 = window.Selection(selections, self._setText, 10)
        selections = [num.encode("utf-8") for num in map(str, range(200, 300))]
        self.select2 = window.Selection(selections, self._setText, 10)
        self.button = window.Button(b"Clear", self._clear)
        self.canvas = DrawableCanvas()

        hbox = window.HBox()
        hbox.addChild(self.input)
        hbox.addChild(self.output)
        hbox.addChild(window.Border(self.button))
        hbox.addChild(window.Border(self.select1))
        hbox.addChild(window.Border(self.select2))

        t1 = window.TextOutputArea(longLines=window.TextOutputArea.WRAP)
        t2 = window.TextOutputArea(longLines=window.TextOutputArea.TRUNCATE)
        t3 = window.TextOutputArea(longLines=window.TextOutputArea.TRUNCATE)
        t4 = window.TextOutputArea(longLines=window.TextOutputArea.TRUNCATE)
        for _t in t1, t2, t3, t4:
            _t.setText(((b"This is a very long string.  " * 3) + b"\n") * 3)

        vp = window.Viewport(t3)
        d = [1]

        def spin():
            vp.xOffset += d[0]
            if vp.xOffset == 0 or vp.xOffset == 25:
                d[0] *= -1

        self.call = task.LoopingCall(spin)
        self.call.start(0.25, now=False)
        hbox.addChild(window.Border(vp))

        vp2 = window.ScrolledArea(t4)
        hbox.addChild(vp2)

        texts = window.VBox()
        texts.addChild(window.Border(t1))
        texts.addChild(window.Border(t2))

        areas = window.HBox()
        areas.addChild(window.Border(self.canvas))
        areas.addChild(texts)

        vbox = window.VBox()
        vbox.addChild(hbox)
        vbox.addChild(areas)
        self.window.addChild(vbox)
        self.terminalSize(self.width, self.height)

    def connectionLost(self, reason):
        self.call.stop()
        insults.TerminalProtocol.connectionLost(self, reason)

    def terminalSize(self, width, height):
        self.width = width
        self.height = height
        self.terminal.eraseDisplay()
        self._redraw()

    def keystrokeReceived(self, keyID, modifier):
        self.window.keystrokeReceived(keyID, modifier)

    def _clear(self):
        self.canvas.clear()

    def _setText(self, text):
        self.input.setText(b"")
        self.output.setText(text)


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


application = service.Application("Window Demo")

makeService(
    {"protocolFactory": ButtonDemo, "telnet": 6023, "ssh": 6022}
).setServiceParent(application)
