
import struct

from twisted.application import internet
from twisted.internet import protocol, interfaces as iinternet, defer
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
BEL =             chr(7)  # Produces an audible or
                          # visible signal (which does
                          # NOT move the print head).
BS =              chr(8)  # Moves the print head one
                          # character position towards
                          # the left margin.
HT =              chr(9)  # Moves the printer to the
                          # next horizontal tab stop.
                          # It remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
LF =             chr(10)  # Moves the printer to the
                          # next print line, keeping the
                          # same horizontal position.
VT =             chr(11)  # Moves the printer to the
                          # next vertical tab stop.  It
                          # remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
FF =             chr(12)  # Moves the printer to the top
                          # of the next page, keeping
                          # the same horizontal position.
CR =             chr(13)  # Moves the printer to the left
                          # margin of the current line.

ECHO  =           chr(1)  # User-to-Server:  Asks the server to send
                          # Echos of the transmitted data.
LINEMODE =      chr(34)   # Allow line buffering to be
                          # negotiated about.

SE =            chr(240)  # End of subnegotiation parameters.
NOP =           chr(241)  # No operation.
DM =            chr(242)  # "Data Mark": The data stream portion
                          # of a Synch.  This should always be
                          # accompanied by a TCP Urgent
                          # notification.
BRK =           chr(243)  # NVT character Break.
IP =            chr(244)  # The function Interrupt Process.
AO =            chr(245)  # The function Abort Output
AYT =           chr(246)  # The function Are You There.
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
IAC =           chr(255)  # Data Byte 255.  Introduces a
                          # telnet command.


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
    def do(self, option):
        pass

    def dont(self, option):
        pass

    def will(self, option):
        pass

    def wont(self, option):
        pass

    def requestNegotiation(self, about, bytes):
        """Send a subnegotiation request.

        @param about: A byte indicating the feature being negotiated.
        @param bytes: Any number of bytes containing specific information
        about the negotiation being requested.  No values in this string
        need to be escaped, as this function will escape any value which
        requires it.
        """

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
    can take on the values "data", "escaped", "command", "newline",
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

    class _OptionState:
        class _Perspective:
            state = 'no'
            negotiating = False
            onResult = None

            def __str__(self):
                return self.state + ('*' * self.negotiating)

        def __init__(self):
            self.us = self._Perspective()
            self.him = self._Perspective()

        def __repr__(self):
            return '<_OptionState us=%s him=%s>' % (self.us, self.him)

    def getOptionState(self, opt):
        return self.options.setdefault(opt, self._OptionState())

    def _do(self, option):
        self._write(IAC + DO + option)

    def _dont(self, option):
        self._write(IAC + DONT + option)

    def _will(self, option):
        self._write(IAC + WILL + option)

    def _wont(self, option):
        self._write(IAC + WONT + option)

    def will(self, option):
        """Indicate our willingness to enable an option.
        """
        s = self.getOptionState(option)
        if s.us.negotiating or s.him.negotiating:
            return defer.fail(AlreadyNegotiating(option))
        elif s.us.state == 'yes':
            return defer.fail(AlreadyEnabled(option))
        else:
            s.us.negotiating = True
            s.us.onResult = d = defer.Deferred()
            self._will(option)
            return d

    def wont(self, option):
        """Indicate we are not willing to enable an option.
        """
        s = self.getOptionState(option)
        if s.us.negotiating or s.him.negotiating:
            return defer.fail(AlreadyNegotiating(option))
        elif s.us.state == 'no':
            return defer.fail(AlreadyDisabled(option))
        else:
            s.us.negotiating = True
            s.us.onResult = d = defer.Deferred()
            self._wont(option)
            return d

    def do(self, option):
        s = self.getOptionState(option)
        if s.us.negotiating or s.him.negotiating:
            return defer.fail(AlreadyNegotiating(option))
        elif s.him.state == 'yes':
            return defer.fail(AlreadyEnabled(option))
        else:
            s.him.negotiating = True
            s.him.onResult = d = defer.Deferred()
            self._do(option)
            return d

    def dont(self, option):
        s = self.getOptionState(option)
        if s.us.negotiating or s.him.negotiating:
            return defer.fail(AlreadyNegotiating(option))
        elif s.him.state == 'no':
            return defer.fail(AlreadyDisabled(option))
        else:
            s.him.negotiating = True
            s.him.onResult = d = defer.Deferred()
            self._dont(option)
            return d

    def requestNegotiation(self, about, bytes):
        bytes = bytes.replace(IAC, IAC * 2)
        self._write(IAC + SB + bytes + IAC + SE)

    def dataReceived(self, data):
        # Most grossly inefficient implementation ever
        for b in data:
            if self.state == 'data':
                if b == IAC:
                    self.state = 'escaped'
                elif b == '\r':
                    self.state = 'newline'
                else:
                    self.applicationDataReceived(b)
            elif self.state == 'escaped':
                if b == IAC:
                    self.applicationDataReceived(b)
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
            elif self.state == 'newline':
                if b == '\n' or b == '\0':
                    self.applicationDataReceived('\n')
                else:
                    self.applicationDataReceived('\r' + b)
                self.state = 'data'
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
            if state.us.onResult is not None:
                d = state.us.onResult
                state.us.onResult = None
                d.errback(reason)
            if state.him.onResult is not None:
                d = state.him.onResult
                state.him.onResult = None
                d.errback(reason)

    def applicationDataReceived(self, bytes):
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

    def telnet_WILL(self, option):
        s = self.getOptionState(option)
        self.willMap[s.him.state, s.him.negotiating](self, s, option)

    def will_no_false(self, state, option):
        # He is unilaterally offering to enable an option.
        if self.allowEnable(option):
            self.enable(option)
            state.him.state = 'yes'
            self._do(option)
        else:
            self._dont(option)

    def will_no_true(self, state, option):
        # Peer agreed to enable an option in response to our request.
        state.him.state = 'yes'
        state.him.negotiating = False
        d = state.him.onResult
        state.him.onResult = None
        d.callback(True)
        self.enable(option)

    def will_yes_false(self, state, option):
        # He is unilaterally offering to enable an already-enabled option.
        # Ignore this.
        pass

    def will_yes_true(self, state, option):
        # This is a bogus state.  It is here for completeness.  It will
        # never be entered.
        assert False, "will_yes_true can never be entered"

    willMap = {('no', False): will_no_false,   ('no', True): will_no_true,
               ('yes', False): will_yes_false, ('yes', True): will_yes_true}

    def telnet_WONT(self, option):
        s = self.getOptionState(option)
        self.wontMap[s.him.state, s.him.negotiating](self, s, option)

    def wont_no_false(self, state, option):
        # He is unilaterally demanding that an already-disabled option be/remain disabled.
        # Ignore this (although we could record it and refuse subsequent enable attempts
        # from our side - he can always refuse them again though, so we won't)
        pass

    def wont_no_true(self, state, option):
        # Peer refused to enable an option in response to our request.
        state.him.negotiating = False
        d = state.him.onResult
        state.him.onResult = None
        d.callback(False)

    def wont_yes_false(self, state, option):
        # Peer is unilaterally demanding that an option be disabled.
        state.him.state = 'no'
        self.disable(option)
        self._dont(option)

    def wont_yes_true(self, state, option):
        # Peer agreed to disable an option at our request.
        state.him.state = 'no'
        state.him.negotiating = False
        self.disable(option)
        d = state.him.onResult
        state.him.onResult = None
        d.callback(True)

    wontMap = {('no', False): wont_no_false,   ('no', True): wont_no_true,
               ('yes', False): wont_yes_false, ('yes', True): wont_yes_true}

    def telnet_DO(self, option):
        s = self.getOptionState(option)
        self.doMap[s.us.state, s.us.negotiating](self, s, option)

    def do_no_false(self, state, option):
        # Peer is unilaterally requesting that we enable an option.
        if self.allowEnable(option):
            state.us.state = 'yes'
            self.enable(option)
            self._will(option)
        else:
            self._wont(option)

    def do_no_true(self, state, option):
        # Peer agreed to enable an option at our request.
        state.us.state = 'yes'
        state.us.negotiating = False
        d = state.us.onResult
        state.us.onResult = None
        d.callback(True)

    def do_yes_false(self, state, option):
        # Peer is unilaterally requesting us to enable an already-enabled option.
        # Ignore this.
        pass

    def do_yes_true(self, state, option):
        # This is a bogus state.  It is here for completeness.  It will never be
        # entered.
        assert False, "do_yes_true can never be entered"

    doMap = {('no', False): do_no_false,   ('no', True): do_no_true,
             ('yes', False): do_yes_false, ('yes', True): do_yes_true}

    def telnet_DONT(self, option):
        s = self.getOptionState(option)
        self.dontMap[s.us.state, s.us.negotiating](self, s, option)

    def dont_no_false(self, state, option):
        # Peer is unilaterally demanding us to disable an already-disabled option.
        # Ignore this.
        pass

    def dont_no_true(self, state, option):
        # This is a bogus state.  It is here for completeness.  It will never be
        # entered.
        assert False, "dont_no_true can never be entered"


    def dont_yes_false(self, state, option):
        # Peer is unilaterally demanding we disable an option.
        state.us.state = 'no'
        self.disable(option)
        self._wont(option)

    def dont_yes_true(self, state, option):
        # Peer acknowledged our notice that we will disable an option.
        state.us.state = 'no'
        state.us.negotiating = False
        d = state.us.onResult
        state.us.onResult = d
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
        self.transport.write(bytes.replace('\n', '\r\n'))

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

    def applicationDataReceived(self, bytes):
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

        for opt in (LINEMODE, NAWS, SUPPRESS_GO_AHEAD):
            self.transport.do(opt).addErrback(log.err)
        for opt in (ECHO,):
            self.transport.will(opt).addErrback(log.err)

        self.protocol = self.protocolFactory(*self.protocolArgs, **self.protocolKwArgs)
        self.protocol.makeConnection(self)

    def allowEnable(self, opt):
        print 'Refusing to allow to enable', repr(opt)
        return False

    def enable(self, opt):
        if opt == LINEMODE:
            self.transport.requestNegotiation(LINEMODE, MODE + chr(TRAPSIG))
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
