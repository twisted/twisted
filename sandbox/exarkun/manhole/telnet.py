
import struct

from twisted.application import internet
from twisted.internet import protocol, interfaces as iinternet, defer
from twisted.protocols import telnet
from twisted.python import components, log

MODE = chr(1)
EDIT = 1
TRAPSIG = 2
MODE_ACK = 4
SOFT_TAB = 8
LIT_ECHO = 16

NAWS = chr(31)
SUPPRESS_GO_AHEAD = chr(3)

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

class TelnetError(Exception):
    pass

class NegotiationError(TelnetError):
    pass

class AlreadyEnabled(NegotiationError):
    pass

class AlreadyDisabled(NegotiationError):
    pass

class AlreadyNegotiating(NegotiationError):
    pass

class TelnetProtocol(protocol.Protocol):
    def __init__(self, proto):
        self.proto = proto

    def unhandledCommand(self, command, argument):
        pass

    def unhandledSubnegotiation(self, command, bytes):
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

    def _write(self, bytes):
        self.transport.write(bytes)

    def requestEnable(self, option):
        s = self.getOptionState(option)
        if s.negotiating:
            return defer.fail(AlreadyNegotiating(option))
        elif s.state == 'yes':
            return defer.fail(AlreadyEnabled(option))
        else:
            s.negotiating = True
            s.onResult = d = defer.Deferred()
            self.do(option)
            return d

    def requestDisable(self, option):
        s = self.getOptionState(option)
        if s.negotiating:
            return defer.fail(AlreadyNegotiating(option))
        elif s.state == 'no':
            return defer.fail(AlreadyDisabled(option))
        else:
            s.negotiating = True
            s.onResult = d = defer.Deferred()
            self.dont(option)
            return d

        return self._disable(option, self.dont)

    def offerDisable(self, option):
        return self._disable(option, self.wont)

    def requestNegotiation(self, about, bytes):
        """Send a subnegotiation request.

        @param about: A byte indicating the feature being negotiated.
        @param bytes: Any number of bytes containing specific information
        about the negotiation being requested.  No values in this string
        need to be escaped, as this function will escape any value which
        requires it.
        """
        bytes = bytes.replace(telnet.IAC, telnet.IAC * 2)
        bytes = bytes.replace(telnet.SE, telnet.IAC + telnet.SE)
        self._write(telnet.IAC + telnet.SB + bytes + telnet.SE)

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
                else:
                    self.commands.append(b)
            elif self.state == 'subnegotiation-escaped':
                if b == SE:
                    self.state = 'data'
                    commands = self.commands
                    del self.commands
                    self.negotiate(commands)
                else:
                    self.state = 'subnegotiation'
                    self.commands.append(b)
            else:
                raise ValueError("How'd you do this?")

    def connectionLost(self, reason):
        for state in self.options.values():
            if state.onResult is not None:
                d = state.onResult
                state.onResult = None
                d.errback(reason)

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

    def do(self, option):
        """Request an option be enabled.
        """
        self._write(IAC + DO + option)

    def dont(self, option):
        """Request an option be disabled.
        """
        self._write(IAC + DONT + option)

    def will(self, option):
        """Indicate that we will enable an option.
        """
        self._write(IAC + WILL + option)

    def wont(self, option):
        """Indicate that we will not enable an option.
        """
        self._write(IAC + WONT + option)

    class _OptionState:
        state = 'no'
        negotiating = False
        onResult = None

    def getOptionState(self, opt):
        return self.options.setdefault(opt, self._OptionState())

    def telnet_WILL(self, option):
        s = self.getOptionState(option)
        self.willMap[s.state, s.negotiating](self, s, option)

    def will_no_false(self, state, option):
        # Peer is requesting an option be enabled
        if self.allowEnable(option):
            self.enable(option)
            state.state = 'yes'
            self.do(option)
        else:
            self.dont(option)

    def will_no_true(self, state, option):
        # Peer agreed to enable an option
        state.state = 'yes'
        state.negotiating = False
        d = state.onResult
        state.onResult = None
        d.callback(True)
        self.enable(option)

    def will_yes_false(self, state, option):
        pass

    def will_yes_true(self, state, option):
        pass

    willMap = {('no', False): will_no_false,   ('no', True): will_no_true,
               ('yes', False): will_yes_false, ('yes', True): will_yes_true}

    def telnet_WONT(self, option):
        s = self.getOptionState(option)
        self.wontMap[s.state, s.negotiating](self, s, option)

    def wont_no_false(self, state, option):
        pass

    def wont_no_true(self, state, option):
        # Peer refused to enable an option
        state.negotiating = False
        d = state.onResult
        state.onResult = None
        d.callback(False)

    def wont_yes_false(self, state, option):
        # Peer is requesting an option be disabled
        state.state = 'no'
        self.disable(option)
        self.dont(option)

    def wont_yes_true(self, state, option):
        # Peer agreed to disable an option
        state.state = 'no'
        state.negotiating = False
        self.disable(option)
        d = state.onResult
        state.onResult = None
        d.callback(True)

    wontMap = {('no', False): wont_no_false,   ('no', True): wont_no_true,
               ('yes', False): wont_yes_false, ('yes', True): wont_yes_true}

    def telnet_DO(self, option):
        s = self.getOptionState(option)
        self.doMap[s.state, s.negotiating](self, s, option)

    def do_no_false(self, state, option):
        # Peer is requesting an option be enabled
        if self.allowEnable(option):
            state.state = 'yes'
            self.enable(option)
            self.will(option)
        else:
            self.wont(option)

    def do_no_true(self, state, option):
        # Peer agreed to enable an option
        state.state = 'yes'
        state.negotiating = False
        d = state.onResult
        state.onResult = None
        d.callback(True)

    def do_yes_false(self, state, option):
        pass

    def do_yes_true(self, state, option):
        pass

    doMap = {('no', False): do_no_false,   ('no', True): do_no_true,
             ('yes', False): do_yes_false, ('yes', True): do_yes_true}

    def telnet_DONT(self, option):
        s = self.getOptionState(option)
        self.dontMap[s.state, s.negotiating](self, s, option)

    def dont_no_false(self, state, option):
        pass

    def dont_no_true(self, state, option):
        pass

    def dont_yes_false(self, state, option):
        # Peer is requesting to disable an option
        state.state = 'no'
        self.disable(option)
        self.wont(option)

    def dont_yes_true(self, state, option):
        # Peer agreed to disable an option
        state.state = 'no'
        state.negotiating = False
        d = state.onResult
        state.onResult = d
        d.callback(True)

    dontMap = {('no', False): dont_no_false,   ('no', True): dont_no_true,
               ('yes', False): dont_yes_false, ('yes', True): dont_yes_true}

    def allowEnable(self, option):
        return False

    def enable(self, option):
        pass

    def disable(self, option):
        pass

class ProtocolTransportMixin:
    def write(self, bytes):
        self.transport.write(bytes)

    def writeSequence(self, seq):
        self.transport.writeSequence(seq)

    def loseConnection(self):
        self.transport.loseConnection()

    def getHost(self):
        return self.transport.getHost()

    def getPeer(self):
        return self.transport.getPeer()

class TelnetTransport(Telnet, ProtocolTransportMixin):
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

    def __init__(self, protocolFactory, *a, **kw):
        Telnet.__init__(self)
        self.protocolFactory = protocolFactory
        self.protocolArgs = a
        self.protocolKwArgs = kw

    def connectionMade(self):
        p = self.protocol = self.protocolFactory(*self.protocolArgs, **self.protocolKwArgs)
        p.makeConnection(self)

    def allowEnable(self, option):
        return self.protocol.allowEnable(option)

    def enable(self, option):
        Telnet.enable(self, option)
        self.protocol.enable(option)

    def disable(self, option):
        Telnet.disable(self, option)
        self.protocol.disable(option)

    def unhandledSubnegotiation(self, command, bytes):
        self.protocol.unhandledSubnegotiation(command, bytes)

    def unhandledCommand(self, command, argument):
        self.protocol.unhandledCommand(command, argument)

    def applicationByteReceived(self, bytes):
        self.protocol.dataReceived(bytes)

    def connectionLost(self, reason):
        Telnet.connectionLost(self, reason)
        self.protocol.connectionLost(reason)
        del self.protocol

class TelnetBootstrapProtocol(TelnetProtocol, ProtocolTransportMixin):
    protocol = None

    def __init__(self, protocolFactory, *args, **kw):
        self.protocolFactory = protocolFactory
        self.protocolArgs = args
        self.protocolKwArgs = kw

    def connectionMade(self):
        self.transport.negotiationMap[NAWS] = self.telnet_NAWS

        for opt in (telnet.LINEMODE, NAWS, SUPPRESS_GO_AHEAD):
            self.transport.requestEnable(opt).addErrback(log.err)

        self.transport.write(telnet.IAC + telnet.WILL + telnet.ECHO)

        self.protocol = self.protocolFactory(*self.protocolArgs, **self.protocolKwArgs)
        self.protocol.makeConnection(self)

    def allowEnable(self, opt):
        return opt in (telnet.LINEMODE, NAWS, SUPPRESS_GO_AHEAD, telnet.ECHO)

    def enable(self, opt):
        if opt == telnet.LINEMODE:
            self.transport.requestNegotiation(telnet.LINEMODE, MODE + chr(TRAPSIG))
        elif opt == NAWS:
            pass
        else:
            print 'enabling', repr(opt)

    def disable(self, opt):
        print 'disabling', repr(opt)

    def telnet_NAWS(self, bytes):
        if len(bytes) == 4:
            width, height = struct.unpack('!HH', ''.join(bytes))
            self.protocol.terminalSize(width, height)
        else:
            log.msg("Wrong number of NAWS bytes")

    def dataReceived(self, data):
        self.protocol.dataReceived(data)
