
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

# Characters gleaned from the various (and conflicting) RFCs.  Not all of these are correct.

NULL =            chr(0)  # No operation.
LF   =           chr(10)  # Moves the printer to the
                          # next print line, keeping the
                          # same horizontal position.
CR =             chr(13)  # Moves the printer to the left
                          # margin of the current line.
BEL =             chr(7)  # Produces an audible or
                          # visible signal (which does
                          # NOT move the print head).
BS  =             chr(8)  # Moves the print head one
                          # character position towards
                          # the left margin.
HT  =             chr(9)  # Moves the printer to the
                          # next horizontal tab stop.
                          # It remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
VT =             chr(11)  # Moves the printer to the
                          # next vertical tab stop.  It
                          # remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
FF =             chr(12)  # Moves the printer to the top
                          # of the next page, keeping
                          # the same horizontal position.
SE =            chr(240)  # End of subnegotiation parameters.
NOP=            chr(241)  # No operation.
DM =            chr(242)  # "Data Mark": The data stream portion
                          # of a Synch.  This should always be
                          # accompanied by a TCP Urgent
                          # notification.
BRK=            chr(243)  # NVT character Break.
IP =            chr(244)  # The function Interrupt Process.
AO =            chr(245)  # The function Abort Output
AYT=            chr(246)  # The function Are You There.
EC =            chr(247)  # The function Erase Character.
EL =            chr(248)  # The function Erase Line
GA =            chr(249)  # The Go Ahead signal.
SB =            chr(250)  # Indicates that what follows is
                          # subnegotiation of the indicated
                          # option.
WILL =          chr(251)  # Indicates the desire to begin
                          # performing, or confirmation that
                          # you are now performing, the
                          # indicated option.
WONT =          chr(252)  # Indicates the refusal to perform,
                          # or continue performing, the
                          # indicated option.
DO =            chr(253)  # Indicates the request that the
                          # other party perform, or
                          # confirmation that you are expecting
                          # the other party to perform, the
                          # indicated option.
DONT =          chr(254)  # Indicates the demand that the
                          # other party stop performing,
                          # or confirmation that you are no
                          # longer expecting the other party
                          # to perform, the indicated option.
IAC =           chr(255)  # Data Byte 255.

class Telnet(protocol.Protocol):
    commandMap = {
        SE: 'SE',
        NOP: 'NOP',
        DM: 'DM',
        BRK: 'BRK',
        IP: 'IP',
        AO: 'AO',
        AYT: 'AYT',
        EC: 'EC',
        EL: 'EL',
        GA: 'GA'}

    _databuf = ''

    # Either 'data' or 'command'
    mode = 'data'

    def dataReceived(self, data):
        data = self._databuf + data
        self._databuf = ''

        chunks = []
        commands = []

        # Most grossly inefficient implementation ever
        while data:
            b = data[0]
            data = data[1:]
            if self.mode == 'data':
                if b == IAC:
                    self.mode = 'escaped'
                else:
                    self.applicationByteReceived(b)
            elif self.mode == 'escaped':
                if b == IAC:
                    self.applicationByteReceived(b)
                    self.mode = 'data'
                elif b == SB:
                    self.mode = 'subnegotiation'
                    self.commands = []
                elif b in (NOP, DM, BREAK, IP, AO, AYT, EC, EL, GA):
                    self.telnetCommandReceived(b, None)
                elif b in (WILL, WONT, DO, DONT):
                    self.state = 'command'
                    self.command = b
                else:
                    raise ValueError("Stumped")
            elif self.mode == 'command':
                self.state = 'data'
                command = self.command
                del self.command
                self.telnetCommandReceived(command, b)
            elif self.mode == 'subnegotiation':
                if b == IAC:
                    self.mode = 'subnegotiation-escaped'
                elif b == SE:
                    self.state = 'data'
                    commands = self.commands
                    del self.commands
                    self.subnegotiationCommandReceived(commands)
                else:
                    self.commands.append(b)
            else:
                raise ValueError("How'd you do this?")



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

    # ITransport or whatever
    def loseConnection(self):
        self.transport.loseConnection()

    def connectionLost(self, reason):
        self.chainedProtocol.connectionLost(reason)

