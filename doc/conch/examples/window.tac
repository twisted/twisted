# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# You can run this .tac file directly with:
#    twistd -ny window.tac

from __future__ import division

import string, random

from twisted.python import log
from twisted.internet import protocol, task
from twisted.application import internet, service
from twisted.cred import checkers, portal

from twisted.conch.insults import insults, window
from twisted.conch.telnet import TelnetTransport, TelnetBootstrapProtocol
from twisted.conch.manhole_ssh import ConchFactory, TerminalRealm

from twisted.internet import reactor

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
        if keyID == '\r' or keyID == '\v':
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
            window.cursor(terminal, self[self.x, self.y])


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
        self.select1 = window.Selection(map(str, range(100)), self._setText, 10)
        self.select2 = window.Selection(map(str, range(200, 300)), self._setText, 10)
        self.button = window.Button("Clear", self._clear)
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
            _t.setText((('This is a very long string.  ' * 3) + '\n') * 3)

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
        self.input.setText('')
        self.output.setText(text)


def makeService(args):
    checker = checkers.InMemoryUsernamePasswordDatabaseDontUse(username="password")

    f = protocol.ServerFactory()
    f.protocol = lambda: TelnetTransport(TelnetBootstrapProtocol,
                                         insults.ServerProtocol,
                                         args['protocolFactory'],
                                         *args.get('protocolArgs', ()),
                                         **args.get('protocolKwArgs', {}))
    tsvc = internet.TCPServer(args['telnet'], f)

    def chainProtocolFactory():
        return insults.ServerProtocol(
            args['protocolFactory'],
            *args.get('protocolArgs', ()),
            **args.get('protocolKwArgs', {}))

    rlm = TerminalRealm()
    rlm.chainedProtocolFactory = chainProtocolFactory
    ptl = portal.Portal(rlm, [checker])
    f = ConchFactory(ptl)
    csvc = internet.TCPServer(args['ssh'], f)

    m = service.MultiService()
    tsvc.setServiceParent(m)
    csvc.setServiceParent(m)
    return m

application = service.Application("Window Demo")

makeService({'protocolFactory': ButtonDemo,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
