
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
    # One of a lot of things
    state = 'data'

    def __init__(self):
        self.options = {}

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
                elif b in (NOP, DM, BREAK, IP, AO, AYT, EC, EL, GA):
                    self.telnetCommandReceived(b, None)
                elif b in (WILL, WONT, DO, DONT):
                    self.state = 'command'
                    self.command = b
                else:
                    raise ValueError("Stumped")
            elif self.state == 'command':
                self.state = 'data'
                command = self.command
                del self.command
                self.telnetCommandReceived(command, b)
            elif self.state == 'subnegotiation':
                if b == IAC:
                    self.state = 'subnegotiation-escaped'
                elif b == SE:
                    self.state = 'data'
                    commands = self.commands
                    del self.commands
                    self.subnegotiationCommandReceived(commands)
                else:
                    self.commands.append(b)
            elif self.state == 'subnegotiation-escaped':
                self.state = 'subnegotiation'
                self.commands.append(b)
            else:
                raise ValueError("How'd you do this?")

    def applicationByteReceived(self, byte):
        pass

    def telnetCommandReceived(self, command, argument):
        cmdfunc = self.commandMap.get(command)
        if cmdfunc is None:
            # Some ill-formed command.  Return us to the data state.
            # After complaining.
            log.msg("Client (%r) sent a bad command: %d" % (self.transport.getPeer(), ord(command)))
            self.state = 'data'
        else:
            if argument is None:
                cmdfunc()
            else:
                cmdfunc(argument)

    def telnet_NOP(self):
        pass

    def telnet_DM(self):
        pass

    def telnet_BREAK(self):
        pass

    def telnet_IP(self):
        pass

    def telnet_AO(self):
        pass

    def telnet_AYT(self):
        pass

    def telnet_EC(self):
        pass

    def telnet_EL(self):
        pass

    def telnet_GA(self):
        pass

    # DO/DONT WILL/WONT are a bit more complex.  They require us to
    # track state to avoid negotiation loops and the like.

    # options is a dict mapping options, as identified by length one
    # strings, to their current state.  The state of an option is
    # composed of four pieces of information, represented by a four
    # tuple.  The first element of the tuple is our view of the state
    # of the option.  The possible values for it are the strings no,
    # wantno, yes, wantyes.  The second element is a boolean
    # indicating a queued state change request.  It only has meaning
    # if the first element is wantno or wantyes.  If it is False,
    # no state change is queued.  If it is True, a state change to
    # the opposite state is queued. The third element indicates the
    # peer's state of this option, and may also be no, wantno, yes,
    # or wantyes.  The fourth element is a boolean indicating a queued
    # state change request.  It only has meaning if the third element
    # is wantno or wantyes.  If it is False, no state change is queued.
    # If it is True, a state change is queued on the peer.

    # Options default to disabled.

    class _OptionState:
        class _Perspective:
            state = stateq = False
        def __init__(self):
            self.us = _Perspective()
            self.him = _Perspective()

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
        return self.options.get(opt, _OptionState())

    def _dodontwillwont(self, option, s, pfx):
        state = self.getOptionState(option)
        view = getattr(state, s)
        getattr(self, '_' + pfx + '_' + view.state)(option, view)

    def _dowill(self, option, s):
        self._dodontwillwont(option, s, 'dowill')

    def _dowill_no(self, option, state)
        if self._shouldAllowEnable(option):
            state.state = 'yes'
            self.do(option)
        else:
            self.dont(option)

    def _dowill_yes(self, option, state):
        pass

    def _dowill_wantno(self, option, state):
        if state.stateq:
            # This is an error state.  The peer is defective.
            state.state = 'yes'
            state.stateq = False
        else:
            # This is an error state.  The peer is defective.
            state.state = 'no'

    def _dowill_wantyes(self, option, state):
        if if state.stateq:
            state.state = 'wantno'
            state.stateq = False
            self.dont(option)
        else:
            state.state = 'yes'

    def _dontwont(self, option, s):
        self._dodontwillwont(option, s, 'dontwont')

    def _dontwont_no(self, option, state):
        pass

    def _dontwont_yes(self, option, state):
        self.setOptionState(option, s, 'no')
        self.dont(option)

    def _dontwont_wantno(self, option, state):
        if self.state[sq]:
            state.state = 'wantyes'
            state.stateq = False
            self.do(option)
        else:
            state.state = 'no'

    def _dontwont_wantyes(self, option, state):
        state.state = 'no'
        if state[sq]:
            state.stateq = False

    def telnet_WILL(self, option):
        self._dowill(option, HIM, HIMQ)

    def telnet_WONT(self, option):
        self._dontwont(option, HIM, HIMQ)

    def telnet_DO(self, option):
        self._dowill(option, US, USQ)

    def telnet_DONT(self, option):
        self._dontwont(option, US, USQ)

US = 0
USQ = 1
HIM = 2
HIMQ = 3

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

