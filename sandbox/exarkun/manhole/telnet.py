
import struct

from twisted.application import internet
from twisted.internet import protocol
from twisted.protocols import telnet
from twisted.python import components, log

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

class ITelnetListener(components.Interface):
    def connectionMade(self):
        """A connection has been established.
        """

    def dataReceived(self, bytes):
        """Some data arrived.
        """

    def subnegotiationCommandReceived(self, bytes):
        """A subnegotiation command was received.
        """

    def connectionLost(self, reason):
        """The connection was lost.
        """

class TelnetListener:
    def __init__(self, proto):
        self.proto = proto

    def connectionMade(self):
        pass

    def dataReceived(self, data):
        pass

    def subnegotiationCommandReceived(self, bytes):
        pass

    def connectionLost(self, reason):
        pass

class Telnet(protocol.Protocol):
    commandMap = {
        WILL: 'WILL',
        WONT: 'WONT',
        DO: 'DO',
        DONT: 'DONT'}

    negotiationMap = {
        }

    # One of a lot of things
    state = 'data'

    def __init__(self):
        self.options = {}
        self.negotiationMap = {}
        self.commandMap = {
            WILL: self.telnet_WILL,
            WONT: self.telnet_WONT,
            DO: self.telnet_DO,
            DONT: self.telnet_DONT}

    def write(self, bytes):
        self.transport.write(bytes)

    def dataReceived(self, data):
        # Most grossly inefficient implementation ever
        for b in data:
            if self.state == 'data':
                if b == IAC:
                    self.state = 'escaped'
                else:
                    self.applicationByteReceived(b)
            elif self.state == 'escaped':
                if b == IAC:
                    self.applicationByteReceived(b)
                    self.state = 'data'
                elif b == SB:
                    self.state = 'subnegotiation'
                    self.commands = []
                elif b in (NOP, DM, BRK, IP, AO, AYT, EC, EL, GA):
                    self.state = 'data'
                    self.commandReceived(b, None)
                elif b in (WILL, WONT, DO, DONT):
                    self.state = 'command'
                    self.command = b
                else:
                    raise ValueError("Stumped", b)
            elif self.state == 'command':
                self.state = 'data'
                command = self.command
                del self.command
                self.commandReceived(command, b)
            elif self.state == 'subnegotiation':
                if b == IAC:
                    self.state = 'subnegotiation-escaped'
                elif b == SE:
                    self.state = 'data'
                    commands = self.commands
                    del self.commands
                    self.negotiate(commands)
                else:
                    self.commands.append(b)
            elif self.state == 'subnegotiation-escaped':
                self.state = 'subnegotiation'
                self.commands.append(b)
            else:
                raise ValueError("How'd you do this?")

    def commandReceived(self, command, argument):
        cmdFunc = self.commandMap.get(command)
        if cmdFunc is None:
            log.msg("Unhandled telnet command: %d %s" % (ord(command), argument and ord(argument)))
        else:
            cmdFunc(argument)

    def applicationByteReceived(self, byte):
        pass

    def negotiate(self, bytes):
        pass

    # DO/DONT WILL/WONT are a bit more complex.  They require us to
    # track state to avoid negotiation loops and the like.

    class _OptionState:
        class _Perspective:
            # 'no', 'yes', 'wantno', 'wantyes'
            state = 'no'
            stateq = False
        def __init__(self):
            self.us = self._Perspective()
            self.him = self._Perspective()

    def do(self, option):
        """Request an option be enabled.
        """
        self.write(IAC + DO + option)

    def dont(self, option):
        """Request an option be disabled.
        """
        self.write(IAC + DONT + option)

    def will(self, option):
        """Indicate that we will enable an option.
        """
        self.write(IAC + WILL + option)

    def wont(self, option):
        """Indicate that we will not enable an option.
        """
        self.write(IAC + WONT + option)

    def getOptionState(self, opt):
        return self.options.get(opt, self._OptionState())

    def _dodontwillwont(self, option, s, pfx, ack, neg):
        state = self.getOptionState(option)
        view = getattr(state, s)
        getattr(self, '_' + pfx + '_' + view.state)(option, view, ack, neg)

    def _dowill(self, option, s, ack, neg):
        self._dodontwillwont(option, s, 'dowill', ack, neg)

    def _dowill_no(self, option, state, ack, neg):
        if self.allowEnable(option):
            self.enable(option)
            state.state = 'yes'
            ack(option)
        else:
            neg(option)

    def _dowill_yes(self, option, state, ack, neg):
        pass

    def _dowill_wantno(self, option, state, ack, neg):
        # This is an error state.  The peer is defective.
        if state.stateq:
            state.state = 'yes'
            state.stateq = False
        else:
            state.state = 'no'

    def _dowill_wantyes(self, option, state, ack, neg):
        if state.stateq:
            state.state = 'wantno'
            state.stateq = False
            neg(option)
        else:
            state.state = 'yes'

    def _dontwont(self, option, s, ack, neg):
        self._dodontwillwont(option, s, 'dontwont', ack, neg)

    def _dontwont_no(self, option, state, ack, neg):
        pass

    def _dontwont_yes(self, option, state, ack, neg):
        state.state = 'no'
        neg(option)

    def _dontwont_wantno(self, option, state, ack, neg):
        if state.stateq:
            state.state = 'wantyes'
            state.stateq = False
            ack(option)
        else:
            state.state = 'no'

    def _dontwont_wantyes(self, option, state, ack, neg):
        state.state = 'no'
        if state.stateq:
            state.stateq = False

    def telnet_WILL(self, option):
        self._dowill(option, 'him', self.do, self.dont)

    def telnet_WONT(self, option):
        self._dontwont(option, 'him', self.do, self.dont)

    def telnet_DO(self, option):
        self._dowill(option, 'us', self.will, self.wont)

    def telnet_DONT(self, option):
        self._dontwont(option, 'us', self.will, self.wont)

    def allowEnable(self, option):
        return False

    def enable(self, option):
        pass

class Telnet2(Telnet):
    handler = None
    handlerFactory = TelnetListener

    def __init__(self, *a, **kw):
        Telnet.__init__(self)
        self.handlerArgs = a
        self.handlerKwArgs = kw

    def connectionMade(self):
        self.handler = self.handlerFactory(self, *self.handlerArgs, **self.handlerKwArgs)
        self.handler.connectionMade()
        for cmdName in 'NOP', 'DM', 'BRK', 'IP', 'AO', 'AYT', 'EC', 'EL', 'GA':
            fname = 'telnet_' + cmdName
            setattr(self, fname, getattr(self.handler, fname, lambda: None))

    def negotiate(self, bytes):
        command, bytes = bytes[0], bytes[1:]
        cmdFunc = self.negotiationMap.get(command)
        if cmdFunc is None:
            self.handler.unknownNegotiation(command, bytes)
        else:
            cmdFunc(bytes)

    def applicationByteReceived(self, bytes):
        self.handler.dataReceived(bytes)

    def connectionLost(self, reason):
        self.handler.connectionLost(reason)
        del self.handler

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

