
import struct

from twisted.application import internet
from twisted.internet import protocol, interfaces as iinternet
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

class ITelnetProtocol(iinternet.IProtocol):
    def unhandledCommand(self, command, argument):
        """A command was received but not understood.
        """

    def unhandledSubnegotiation(self, bytes):
        """A subnegotiation command was received but not understood.
        """

    def allowEnable(self, option):
        """Indicate whether or not the given option can be enabled.

        This will never be called with a currently enabled option.
        """

    def enable(self, option):
        """Enable the given option.

        This will only be called after allowEnable(option) returns True.
        """

    def disable(self, option):
        """Disable the given option.
        """

class ITelnetTransport(iinternet.ITransport):
    def requestEnable(self, option):
        pass

    def requestDisable(self, option):
        pass

class TelnetProtocol(protocol.Protocol):
    def __init__(self, proto):
        self.proto = proto

    def unhandledCommand(self, command, argument):
        pass

    def unhandledSubnegotiation(self, bytes):
        pass

    def allowEnable(self, option):
        return False

    def enable(self, option):
        pass

    def disable(self, option):
        pass


class Telnet(protocol.Protocol):
    """
    @ivar commandMap: A mapping of bytes to callables.  When a
    telnet command is received, the command byte (the first byte
    after IAC) is looked up in this dictionary.  If a callable is
    found, it is invoked with the argument of the command, or None
    if the command takes no argument.  Values should be added to
    this dictionary if commands wish to be handled.  By default,
    only WILL, WONT, DO, and DONT are handled.  These should not
    be overridden, as this class handles them correctly and
    provides an API for interacting with them.

    @ivar negotiationMap: A mapping of bytes to callables.  When
    a subnegotiation command is received, the command byte (the
    first byte after SE) is looked up in this dictionary.  If
    a callable is found, it is invoked with the argument of the
    subnegotiation.  Values should be added to this dictionary if
    subnegotiations are to be handled.  By default, no values are
    handled.

    @ivar options: A mapping of option bytes to their current
    state.  This state is likely of little use to user code.
    Changes should not be made to it.

    @ivar state: A string indicating the current parse state.  It
    can take on the values "data", "escaped", "command",
    "subnegotiation", and "subnegotiation-escaped".  Changes
    should not be made to it.

    @ivar transport: This protocol's transport object.
    """

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

    def requestEnable(self, option):
        s = self.getOptionState(option)
        if s.us.state == 'no':
            s.him.state = 'wantyes'
            s.onResult = d = defer.Deferred()
            self.do(option)
            return d
        elif s.us.state == 'yes':
            return defer.fail(AlreadyEnabled(option))
        elif s.us.state == 'wantno':
            if s.us.stateq:
                return defer.fail(AlreadyQueued(option))
            else:
                s.him.stateq = True
                s.onResult = d = defer.Deferred()
                return d
        elif s.us.state == 'wantyes':
            if s.us.stateq:
                s.him.stateq = False
            else:
                return defer.fail(AlreadyNegotiating(option))
        else:
            raise ValueError("Illegal state")

    def requestDisable(self, option):
        s = self.getOptionState(option)
        if s.us.state == 'no':
            return defer.fail(AlreadyDisabled(option))
        elif s.us.state == 'yes':
            s.him.state = 'wantno'
            s.onResult = d = defer.Deferred()
            self.dont(option)
            return d
        elif s.us.state == 'wantno':
            if s.us.stateq:
                s.him.stateq = False
            else:
                return defer.fail(AlreadyNegotiating(option))
        elif s.us.state == 'wantyes':
            if s.us.stateq:
                return defer.fail(AlreadyQueued(option))
            else:
                s.him.stateq = True
        else:
            raise ValueError("Illegal state")

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

    def applicationByteReceived(self, byte):
        """Called with application-level data.
        """

    def unhandledCommand(self, command, argument):
        """Called for commands for which no handler is installed.
        """

    def commandReceived(self, command, argument):
        cmdFunc = self.commandMap.get(command)
        if cmdFunc is None:
            self.unhandledCommand(command, argument)
        else:
            cmdFunc(argument)

    def unhandledSubnegotiation(self, command, bytes):
        """Called for subnegotiations for which no handler is installed.
        """

    def negotiate(self, bytes):
        command, bytes = bytes[0], bytes[1:]
        cmdFunc = self.negotiationMap.get(command)
        if cmdFunc is None:
            self.unhandledSubnegotiation(command, bytes)
        else:
            cmdFunc(bytes)

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
        return self.options.setdefault(opt, self._OptionState())

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

    def disable(self, option):
        pass

class TelnetTransport(Telnet):
    """
    @ivar protocol: An instance of the protocol to which this
    transport is connected, or None before the connection is
    established and after it is lost.

    @ivar protocolFactory: A callable which returns protocol
    instances.  This will be invoked when a connection is
    established.  It is passed the TelnetTransport instance
    as the first argument, and any additional arguments which
    were passed to __init__.

    @ivar protocolArgs: A tuple of additional arguments to
    pass to protocolFactory.

    @ivar protocolKwArgs: A dictionary of additional arguments
    to pass to protocolFactory.
    """

    protocol = None
    protocolFactory = None

    def __init__(self, *a, **kw):
        Telnet.__init__(self)
        self.protocolArgs = a
        self.protocolKwArgs = kw

    def connectionMade(self):
        p = self.protocol = self.protocolFactory(self)
        p.makeConnection(self)

    def allowEnable(self, option):
        return self.protocol.allowEnable(option)

    def enable(self, option):
        Telnet.enable(self, option)
        self.protocol.enable(option)

    def disable(self, option):
        Telnet.disable(self, option)
        self.protocol.disable(option)

    def unhandledSubnegotiation(self, bytes):
        self.protocol.unhandledSubnegotiation(bytes)

    def unhandledCommand(self, command, argument):
        self.protocol.unhandledCommand(command, argument)

    def applicationByteReceived(self, bytes):
        self.protocol.dataReceived(bytes)

    def connectionLost(self, reason):
        self.protocol.connectionLost(reason)
        del self.protocol

class BootstrapProtocol(TelnetProtocol):
    protocolFactory = None

    def __init__(self, proto, *a, **kw):
        self.proto = self.protocolFactory(self, proto, *a, **kw)

class TelnetBootstrapProtocol(TelnetTransport):
    def connectionMade(self):
        TelnetTransport.connectionMade(self)
        for opt in (telnet.LINEMODE, telnet.ECHO, telnet.NAWS):
            self.requestEnable(opt)

    def allowEnable(self, opt):
        return opt in (telnet.LINEMODE, telnet.ECHO, telnet.NAWS)

    def enable(self, opt):
        pass

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

