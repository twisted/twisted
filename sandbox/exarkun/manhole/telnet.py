
import struct

from twisted.application import internet
from twisted.internet import protocol
from twisted.protocols import telnet

MODE = '\x01'
EDIT = 1
TRAPSIG = 2
MODE_ACK = 4
SOFT_TAB = 8
LIT_ECHO = 16

NAWS = '\x1f'
SUPPRESS_GO_AHEAD = '\x03'

class TelnetBootstrapProtocol(telnet.Telnet):
    protocol = None

    def connectionMade(self):
        self.transport.write(telnet.IAC + telnet.DO + telnet.LINEMODE)
        self.transport.write(telnet.IAC + telnet.WILL + telnet.ECHO)
        self.transport.write(telnet.IAC + telnet.DO + NAWS)
        p = self.protocol()
        p.makeConnection(self)
        self.chainedProtocol = p

    def iacSBchunk(self, chunk):
        if chunk[0] == NAWS:
            if len(chunk) == 6:
                width, height = struct.unpack('!HH', chunk[1:-1])
                self.chainedProtocol.handler.terminalSize(width, height)

    def iac_WILL(self, feature):
        if feature == telnet.LINEMODE:
            self.write(telnet.IAC + telnet.SB + telnet.LINEMODE + MODE + chr(TRAPSIG) + telnet.IAC + telnet.SE)
        elif feature == telnet.ECHO:
            self.write(telnet.IAC + telnet.DONT + telnet.ECHO)

    def iac_WONT(self, feature):
        pass

    def iac_DO(self, feature):
        if feature == telnet.GA:
            self.write(telnet.IAC + telnet.WILL + SUPPRESS_GO_AHEAD)

    def iac_DONT(self, feature):
        pass

    def processChunk(self, bytes):
        self.chainedProtocol.dataReceived(bytes)

