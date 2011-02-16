# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.conch.telnet import TelnetTransport, TelnetProtocol
from twisted.internet.protocol import ServerFactory
from twisted.application.internet import TCPServer
from twisted.application.service import Application

class TelnetEcho(TelnetProtocol):
    def enableRemote(self, option):
        self.transport.write("You tried to enable %r (I rejected it)\r\n" % (option,))
        return False


    def disableRemote(self, option):
        self.transport.write("You disabled %r\r\n" % (option,))


    def enableLocal(self, option):
        self.transport.write("You tried to make me enable %r (I rejected it)\r\n" % (option,))
        return False


    def disableLocal(self, option):
        self.transport.write("You asked me to disable %r\r\n" % (option,))


    def dataReceived(self, data):
        self.transport.write("I received %r from you\r\n" % (data,))


factory = ServerFactory()
factory.protocol = lambda: TelnetTransport(TelnetEcho)
service = TCPServer(8023, factory)

application = Application("Telnet Echo Server")
service.setServiceParent(application)
