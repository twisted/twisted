# -*- test-case-name: twisted.mail.test.test_pop3client -*-
# Copyright (c) 2001-2004 Divmod Inc.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A POP3 client protocol implementation.

Don't use this module directly.  Use twisted.mail.pop3 instead.

@author: Jp Calderone
"""

import re
from hashlib import md5

from twisted.python import log
from twisted.internet import defer
from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import error
from twisted.internet import interfaces

OK = '+OK'
ERR = '-ERR'



class POP3ClientError(Exception):
    """
    The base class for all exceptions raised by POP3Client.
    """



class InsecureAuthenticationDisallowed(POP3ClientError):
    """
    An error indicating secure authentication was required but no mechanism
    could be found.
    """



class TLSError(POP3ClientError):
    """
    An error indicating secure authentication was required but either the
    transport does not support TLS or no TLS context factory was supplied.
    """



class TLSNotSupportedError(POP3ClientError):
    """
    An error indicating secure authentication was required but the server does
    not support TLS.
    """



class ServerErrorResponse(POP3ClientError):
    """
    An error indicating that the server returned an error response to a request.

    @ivar consumer: See L{__init__}
    """
    def __init__(self, reason, consumer=None):
        """
        @type reason: C{str}
        @param reason: The server response minus the status indicator.

        @type consumer: callable that takes C{object}
        @param consumer: (optional) The function meant to handle the values
            for a multi-line response.
        """
        POP3ClientError.__init__(self, reason)
        self.consumer = consumer



class LineTooLong(POP3ClientError):
    """
    An error indicating that the server sent an extremely long line.
    """



class _ListSetter:
    """
    A utility class to construct a list from a multi-line response accounting
    for deleted messages.

    POP3 responses sometimes occur in the form of a list of lines containing
    two pieces of data, a message index and a value of some sort.  When a
    message is deleted, it is omitted from these responses.  The setitem
    method of this class is meant to be called with these two values.  In the
    cases where indices are skipped, it takes care of padding out the missing
    values with None.

    @ivar L: See L{__init__}
    """

    def __init__(self, L):
        """
        @type L: C{list} of C{object}
        @param L: The list being constructed.  An empty list should be
            passed in.
        """
        self.L = L


    def setitem(self, (item, value)):
        """
        Add the value at the specified position padding out missing entries.

        @type item: C{int}
        @param item: The 0-based index in the list at which the value should
            be placed.

        @type value: C{object}
        @param value: The value to put in the list.
        """
        diff = item - len(self.L) + 1
        if diff > 0:
            self.L.extend([None] * diff)
        self.L[item] = value



def _statXform(line):
    """
    Parse the response to a STAT command.

    @type line: C{str}
    @param line: The response from the server to a STAT command minus the
        status indicator.

    @rtype: (C{int}, C{int})
    @return: The number of messages in the mailbox and the size of the mailbox.
    """
    numMsgs, totalSize = line.split(None, 1)
    return int(numMsgs), int(totalSize)



def _listXform(line):
    """
    Parse a line of the response to a LIST command.

    The line from the LIST response consists of a 1-based message number
    followed by a size.

    @type line: C{str}
    @param line: A non-initial line from the multi-line response to a LIST
        command.

    @rtype: (C{int}, C{int})
    @return: The 0-based index of the message and the size of the message.
    """
    index, size = line.split(None, 1)
    return int(index) - 1, int(size)



def _uidXform(line):
    """
    Parse a line of the response to a UIDL command.

    The line from the UIDL response consists of a 1-based message number
    followed by a unique id.

    @type line: C{str}
    @param line: A non-initial line from the multi-line response to a UIDL
        command.

    @rtype: (C{int}, C{str})
    @return: The 0-based index of the message and the unique identifier
        for the message.
    """
    index, uid = line.split(None, 1)
    return int(index) - 1, uid



def _codeStatusSplit(line):
    """
    Parse the first line of a multi-line server response.

    @type line: C{str}
    @param line: The first line of a multi-line server response.

    @rtype: (C{str}, C{str})
    @return: The status indicator and the rest of the server response.
    """
    parts = line.split(' ', 1)
    if len(parts) == 1:
        return parts[0], ''
    return parts



def _dotUnquoter(line):
    """
    Remove a byte-stuffed termination character at the beginning of a line if
    present.

    When the termination character (C{'.'}) appears at the beginning of a line,
    the server byte-stuffs it by adding another termination character to
    avoid confusion with the terminating sequence (C{'.\\r\\n'}).

    @type line: C{str}
    @param line: A received line.

    @rtype: C{str}
    @return: The line without the byte-stuffed termination character at the
        beginning if it was present. Otherwise, the line unchanged.
    """
    if line.startswith('..'):
        return line[1:]
    return line



class POP3Client(basic.LineOnlyReceiver, policies.TimeoutMixin):
    """
    A POP3 client protocol.

    Instances of this class provide a convenient, efficient API for
    retrieving and deleting messages from a POP3 server.

    This API provides a pipelining interface but POP3 pipelining
    on the network is not yet supported.

    @type startedTLS: C{bool}
    @ivar startedTLS: An indication of whether TLS has been negotiated
        successfully.

    @type allowInsecureLogin: C{bool}
    @ivar allowInsecureLogin: An indication of whether plaintext login should
        be allowed if the server offers no authentication challenge and if the
        transport does not offer any protection via encryption.

    @type serverChallenge: C{str} or C{None}
    @ivar serverChallenge: The challenge received in the server greeting.

    @type timeout: C{int}
    @ivar timeout: The number of seconds to wait on a response from the server
        before timing out a connection.  If the number is <= 0, no timeout
        checking will be performed.

    @type _capCache: C{NoneType} or C{dict} of C{str} -> C{NoneType}
        or C{list} of C{str}
    @ivar _capCache: The cached server capabilities.  Capabilities are not
        allowed to change during the session (except when TLS is negotiated),
        so the first response to a capabilities command can be used for
        later lookups.

    @type _challengeMagicRe: regular expression object
    @ivar _challengeMagicRe: A regular expression which matches the
        challenge in the server greeting.

    @type _blockedQueue: C{NoneType} or C{list} of (L{Deferred},
        callable which results in a L{Deferred}, C{tuple})
    @ivar _blockedQueue: A list of blocked commands.  While a command is
        awaiting a response from the server, other commands are blocked.  When
        no command is outstanding, C{_blockedQueue} is set to None.  Otherwise,
        it contains a list of information about blocked commands.  Each list
        entry provides the following information about a blocked command: the
        deferred that should be called when the response to the command is
        received, the function that sends the command, and the arguments to
        the function.

    @type _waiting: L{Deferred} or C{NoneType}
    @ivar _waiting: A deferred which fires when the response to the
        outstanding command is received from the server.

    @type _timedOut: C{bool}
    @ivar _timedOut: An indication of whether the connection was dropped
        because of a timeout.

    @type _greetingError: C{str} or C{NoneType}
    @ivar _greetingError: The server greeting minus the status indicator, when
        the connection was dropped because of an error in the server greeting.
        Otherwise, None.

    @type state: C{str}
    @ivar state: The state which indicates what type of response is expected
        from the server.  Valid states are: 'WELCOME', 'WAITING', 'SHORT',
        'LONG_INITIAL', 'LONG'.

    @type _xform: C{NoneType} or callable that takes C{str} and
        returns C{object}
    @ivar _xform: The transform function which is used to convert each
        line of a multi-line response into usable values for use by the
        consumer function.  If None, each line of the multi-line response
        is sent directly to the consumer function.

    @type _consumer: callable that takes C{object}
    @ivar _consumer: The consumer function which is used to store the
        values derived by the transform function from each line of a
        multi-line response into a list.
    """
    startedTLS = False
    allowInsecureLogin = False
    timeout = 0
    serverChallenge = None

    _capCache = None
    _challengeMagicRe = re.compile('(<[^>]+>)')
    _blockedQueue = None
    _waiting = None
    _timedOut = False
    _greetingError = None

    def _blocked(self, f, *a):
        """
        Block a command, if necessary.

        If commands are being blocked, append information about the function
        which sends the command to a list and return a deferred that will be
        chained with the return value of the function when it eventually runs.
        Otherwise, set up for subsequent commands to be blocked and return
        None.

        @type f: callable
        @param f: A function which sends a command.

        @type a: C{tuple}
        @param a: Arguments to the function.

        @rtype: C{NoneType} or L{Deferred}
        @return: None if the command can run immediately.  Otherwise,
            a deferred that will eventually trigger with the return value of
            the function.
         """
        if self._blockedQueue is not None:
            d = defer.Deferred()
            self._blockedQueue.append((d, f, a))
            return d
        self._blockedQueue = []
        return None


    def _unblock(self):
        """
        Send the next blocked command.

        If there are no more commands in the blocked queue, set up for the next
        command to be sent immediately.
        """
        if self._blockedQueue == []:
            self._blockedQueue = None
        elif self._blockedQueue is not None:
            _blockedQueue = self._blockedQueue
            self._blockedQueue = None

            d, f, a = _blockedQueue.pop(0)
            d2 = f(*a)
            d2.chainDeferred(d)
            # f is a function which uses _blocked (otherwise it wouldn't
            # have gotten into the blocked queue), which means it will have
            # re-set _blockedQueue to an empty list, so we can put the rest
            # of the blocked queue back into it now.
            self._blockedQueue.extend(_blockedQueue)


    def sendShort(self, cmd, args):
        """
        Send a POP3 command to which a short response is expected.

        Block all further commands from being sent until the response is
        received.  Transition the state to SHORT.

        @type cmd: C{str}
        @param cmd: A POP3 command.

        @type args: C{str}
        @param args: The command arguments.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the entire response is received.
            On an okay response, it returns the response from the server minus
            the status indicator.  On an error response, it issues a server
            error response failure with the response from the server minus the
            status indicator.
        """
        d = self._blocked(self.sendShort, cmd, args)
        if d is not None:
            return d

        if args:
            self.sendLine(cmd + ' ' + args)
        else:
            self.sendLine(cmd)
        self.state = 'SHORT'
        self._waiting = defer.Deferred()
        return self._waiting


    def sendLong(self, cmd, args, consumer, xform):
        """
        Send a POP3 command to which a multi-line response is expected.

        Block all further commands from being sent until the entire response is
        received.  Transition the state to LONG_INITIAL.

        @type cmd: C{str}
        @param cmd: A POP3 command.

        @type args: C{str}
        @param args: The command arguments.

        @type _consumer: callable that takes C{object}
        @param _consumer: A consumer function which should be used to put
            the values derived by a transform function from each line of the
            multi-line response into a list.

        @type xform: C{NoneType} or callable that takes C{str} and
            returns C{object}
        @param xform: A transform function which should be used to transform
            each line of the multi-line response into usable values for use by
            a consumer function.  If None, each line of the multi-line response
            should be sent directly to the consumer function.

        @rtype: L{Deferred} which successfully fires with callable that takes
            C{object} and fails with L{ServerErrorResponse}
        @return: A deferred which fires when the entire response is received.
            On an okay response, it returns the consumer function.  On an error
            response, it issues a server error response failure with the
            response from the server minus the status indicator and the
            consumer function.
        """
        d = self._blocked(self.sendLong, cmd, args, consumer, xform)
        if d is not None:
            return d

        if args:
            self.sendLine(cmd + ' ' + args)
        else:
            self.sendLine(cmd)
        self.state = 'LONG_INITIAL'
        self._xform = xform
        self._consumer = consumer
        self._waiting = defer.Deferred()
        return self._waiting


    # Twisted protocol callback
    def connectionMade(self):
        """
        Wait for a greeting from the server after the connection has been made.

        Start the connection in the WELCOME state.
        """
        if self.timeout > 0:
            self.setTimeout(self.timeout)

        self.state = 'WELCOME'
        self._blockedQueue = []


    def timeoutConnection(self):
        """
        Drop the connection when the server does not respond in time.
        """
        self._timedOut = True
        self.transport.loseConnection()


    def connectionLost(self, reason):
        """
        Clean up when the connection has been lost.

        When the loss of connection was initiated by the client due to a
        timeout, the L{_timedOut} flag will be set.  When it was initiated by
        the client due to an error in the server greeting, L{_greetingError}
        will be set to the server response minus the status indicator.

        @type reason: L{Failure}
        @param reason: The reason the connection was terminated.
        """
        if self.timeout > 0:
            self.setTimeout(None)

        if self._timedOut:
            reason = error.TimeoutError()
        elif self._greetingError:
            reason = ServerErrorResponse(self._greetingError)

        d = []
        if self._waiting is not None:
            d.append(self._waiting)
            self._waiting = None
        if self._blockedQueue is not None:
            d.extend([deferred for (deferred, f, a) in self._blockedQueue])
            self._blockedQueue = None
        for w in d:
            w.errback(reason)


    def lineReceived(self, line):
        """
        Pass a received line to a state machine function and
        transition to the next state.

        @type line: C{str}
        @param line: A received line.
        """
        if self.timeout > 0:
            self.resetTimeout()

        state = self.state
        self.state = None
        state = getattr(self, 'state_' + state)(line) or state
        if self.state is None:
            self.state = state


    def lineLengthExceeded(self, buffer):
        """
        Drop the connection when a server response is too long.

        @type buffer: C{str}
        @param buffer: A received line which exceeds the maximum line length.
        """
        # XXX - We need to be smarter about this
        if self._waiting is not None:
            waiting, self._waiting = self._waiting, None
            waiting.errback(LineTooLong())
        self.transport.loseConnection()


    # POP3 Client state logic - don't touch this.
    def state_WELCOME(self, line):
        """
        Handle server responses for the WELCOME state in which the server
        greeting is expected.

        WELCOME is the first state.  The server should send one line of text
        with a greeting and possibly an APOP challenge.  Transition the state
        to WAITING.

        @type line: C{str}
        @param line: A line received from the server.

        @rtype: C{str}
        @return: The next state.
        """
        code, status = _codeStatusSplit(line)
        if code != OK:
            self._greetingError = status
            self.transport.loseConnection()
        else:
            m = self._challengeMagicRe.search(status)

            if m is not None:
                self.serverChallenge = m.group(1)

            self.serverGreeting(status)

        self._unblock()
        return 'WAITING'


    def state_WAITING(self, line):
        """
        Log an error for server responses received in the WAITING state during
        which the server is not expected to send anything.

        @type line: C{str}
        @param line: A line received from the server.
        """
        log.msg("Illegal line from server: " + repr(line))


    def state_SHORT(self, line):
        """
        Handle server responses for the SHORT state in which the server is
        expected to send a single line response.

        Parse the response and fire the deferred which is waiting on receipt of
        a complete response.  Transition the state back to WAITING.

        @type line: C{str}
        @param line: A line received from the server.

        @rtype: C{str}
        @return: The next state.
        """
        code, status = _codeStatusSplit(line)
        deferred, self._waiting = self._waiting, None
        self._unblock()
        code, status = _codeStatusSplit(line)
        if code == OK:
            deferred.callback(status)
        else:
            deferred.errback(ServerErrorResponse(status))
        return 'WAITING'


    def state_LONG_INITIAL(self, line):
        """
        Handle server responses for the LONG_INITIAL state in which the server
        is expected to send the first line of a multi-line response.

        Parse the response.  On an okay response, transition the state to
        LONG.  On an error response, cleanup and transition the state to
        WAITING.

        @type line: C{str}
        @param line: A line received from the server.

        @rtype: C{str}
        @return: The next state.
        """
        code, status = _codeStatusSplit(line)
        if code == OK:
            return 'LONG'
        consumer = self._consumer
        deferred = self._waiting
        self._consumer = self._waiting = self._xform = None
        self._unblock()
        deferred.errback(ServerErrorResponse(status, consumer))
        return 'WAITING'


    def state_LONG(self, line):
        """
        Handle server responses for the LONG state in which the server is
        expected to send a non-initial line of a multi-line response.

        On receipt of the last line of the response, clean up, fire the
        deferred which is waiting on receipt of a complete response, and
        transition the state to WAITING. Otherwise, pass the line to the
        transform function, if provided, and then the consumer function.

        @type line: C{str}
        @param line: A line received from the server.

        @rtype: C{str}
        @return: The next state.
        """
        # This is the state for each line of a long response.
        if line == '.':
            consumer = self._consumer
            deferred = self._waiting
            self._consumer = self._waiting = self._xform = None
            self._unblock()
            deferred.callback(consumer)
            return 'WAITING'
        else:
            if self._xform is not None:
                self._consumer(self._xform(line))
            else:
                self._consumer(line)
            return 'LONG'


    # Callbacks - override these
    def serverGreeting(self, greeting):
        """
        Handle the server greeting.

        @type greeting: C{str}
        @param greeting: The server greeting minus the status indicator.
            For servers implementing APOP authentication, this will contain a
            challenge string.
        """


    # External API - call these (most of 'em anyway)
    def startTLS(self, contextFactory=None):
        """
        Switch to encrypted communication using TLS or SSL.

        The first step of switching to encrypted communication is obtaining
        the server's capabilities.  When that is complete, the L{_startTLS}
        callback function continues the switching process.

        @type contextFactory: L{ClientContextFactory} or C{NoneType}
        @param contextFactory: (optional) The context factory with which to
        negotiate TLS.  If not provided, try to create a new one.

        @rtype: L{Deferred} which successfully results in a
            C{dict} of C{str} -> C{NoneType} or C{list} of C{str} or fails with
            L{TLSError}
        @return: A deferred which fires when the transport has been
            secured according to the given contextFactory with the server
            capabilities, or which fails with a TLS error if the transport
            cannot be secured.
        """
        tls = interfaces.ITLSTransport(self.transport, None)
        if tls is None:
            return defer.fail(TLSError(
                "POP3Client transport does not implement "
                "interfaces.ITLSTransport"))

        if contextFactory is None:
            contextFactory = self._getContextFactory()

        if contextFactory is None:
            return defer.fail(TLSError(
                "POP3Client requires a TLS context to "
                "initiate the STLS handshake"))

        d = self.capabilities()
        d.addCallback(self._startTLS, contextFactory, tls)
        return d


    def _startTLS(self, caps, contextFactory, tls):
        """
        Continue the process of switching to encrypted communication.

        This callback function runs after the server capabilities are received.

        The next step is sending the server an STLS command to request a
        switch to encrypted communication.  When an okay response is received,
        the L{_startedTLS} callback function completes the switch to encrypted
        communication. Then, the new server capabilities are requested.

        @type caps: C{dict} of C{str} -> C{NoneType} or C{list} of C{str}
        @param caps: The server capabilities.

        @type contextFactory: L{ClientContextFactory}
        @param contextFactory: A context factory with which to negotiate TLS.

        @type tls: L{ITLSTransport}
        @param tls: A TCP transport that supports switching to TLS midstream.

        @rtype: L{Deferred} which successfully triggers with
            C{dict} of C{str} -> C{NoneType} or C{list} of C{str} or fails with
            L{TLSNotSupportedError}
        @return: A deferred which successfully fires when the response from
            the server to the request to start TLS has been received and the
            new server capabilities have been received or fails when the server
            does not support TLS.
        """
        assert not self.startedTLS, "Client and Server are currently communicating via TLS"

        if 'STLS' not in caps:
            return defer.fail(TLSNotSupportedError(
                "Server does not support secure communication "
                "via TLS / SSL"))

        d = self.sendShort('STLS', None)
        d.addCallback(self._startedTLS, contextFactory, tls)
        d.addCallback(lambda _: self.capabilities())
        return d


    def _startedTLS(self, result, context, tls):
        """
        Complete the process of switching to encrypted communication.

        This callback function runs after the response to the STLS command has
        been received.

        The final steps are discarding the cached capabilities and initiating
        TLS negotiation on the transport.

        @type result: C{dict} of C{str} -> C{NoneType} or C{list} of C{str}
        @param result: The server capabilities.

        @type contextFactory: L{ClientContextFactory}
        @param contextFactory: A context factory with which to negotiate TLS.

        @type tls: L{ITLSTransport}
        @param tls: A TCP transport that supports switching to TLS midstream.

        @rtype: C{dict} of C{str} -> C{NoneType} or C{list} of C{str}
        @return: The server capabilities.
        """
        self.transport = tls
        self.transport.startTLS(context)
        self._capCache = None
        self.startedTLS = True
        return result


    def _getContextFactory(self):
        """
        Get a context factory with which to negotiate TLS.

        @rtype: L{ClientContextFactory} or C{NoneType}
        @return: A context factory or None if TLS is not supported on the
            client.
        """
        try:
            from twisted.internet import ssl
        except ImportError:
            return None
        else:
            context = ssl.ClientContextFactory()
            context.method = ssl.SSL.TLSv1_METHOD
            return context


    def login(self, username, password):
        """
        Log into the server.

        If APOP is available it will be used.  Otherwise, if TLS is
        available, an encrypted session will be started and plaintext
        login will proceed.  Otherwise, if L{allowInsecureLogin} is set,
        insecure plaintext login will proceed.  Otherwise,
        L{InsecureAuthenticationDisallowed} will be raised.

        The first step of logging into the server is obtaining the server's
        capabilities.  When that is complete, the L{_login} callback function
        continues the login process.

        @type username: C{str}
        @param username: The username with which to log in.

        @type password: C{str}
        @param password: The password with which to log in.

        @rtype: C{Deferred} which successfully fires with C{str}
        @return: A deferred which fires when the login process is complete.
            On a successful login, it returns the server's response minus the
            status indicator.
        """
        d = self.capabilities()
        d.addCallback(self._login, username, password)
        return d


    def _login(self, caps, username, password):
        """
        Continue the process of logging into the server.

        This callback function runs after the server capabilities are received.

        If the server provided a challenge in the greeting, proceed with an
        APOP login.  Otherwise, if the server and the transport support
        encrypted communication, try to switch to TLS or SSL and then complete
        the login process with the L{_loginTLS} callback function.  Otherwise,
        if insecure authentication is allowed, do a plaintext login.
        Otherwise, fail with an L{InsecureAuthenticationDisallowed} error.

        @type caps: C{dict} of C{str} -> C{NoneType} or C{list} of C{str}
        @param caps: The server capabilities.

        @type username: C{str}
        @param username: The username with which to log in.

        @type password: C{str}
        @param password: The password with which to log in.

        @rtype: C{Deferred} which successfully fires with C{str}
        @return: A deferred which fires when the login process is complete.
            On a successful login, it returns the server's response minus the
            status indicator.
        """
        if self.serverChallenge is not None:
            return self._apop(username, password, self.serverChallenge)

        tryTLS = 'STLS' in caps

        #If our transport supports switching to TLS, we might want to try to switch to TLS.
        tlsableTransport = interfaces.ITLSTransport(self.transport, None) is not None

        # If our transport is not already using TLS, we might want to try to switch to TLS.
        nontlsTransport = interfaces.ISSLTransport(self.transport, None) is None

        if not self.startedTLS and tryTLS and tlsableTransport and nontlsTransport:
            d = self.startTLS()

            d.addCallback(self._loginTLS, username, password)
            return d

        elif self.startedTLS or not nontlsTransport or self.allowInsecureLogin:
            return self._plaintext(username, password)
        else:
            return defer.fail(InsecureAuthenticationDisallowed())


    def _loginTLS(self, res, username, password):
        """
        Do a plaintext login over an encrypted transport.

        This callback function runs after the transport switches to encrypted
        communication.

        @type res: C{dict} of C{str} -> C{NoneType} or C{list} of C{str}
        @param res: The server capabilities.

        @type username: C{str}
        @param username: The username with which to log in.

        @type password: C{str}
        @param password: The password with which to log in.

        @rtype: C{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server accepts the username
            and password or fails when the server rejects either.  On a
            successful login, it returns the server's response minus the
            status indicator.
        """
        return self._plaintext(username, password)


    def _plaintext(self, username, password):
        """
        Perform a plaintext login.

        @type username: C{str}
        @param username: The username with which to log in.

        @type password: C{str}
        @param password: The password with which to log in.

        @rtype: C{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server accepts the username
            and password or fails when the server rejects either.  On a
            successful login, it returns the server's response minus the
            status indicator.
        """
        return self.user(username).addCallback(lambda r: self.password(password))


    def _apop(self, username, password, challenge):
        """
        Perform an APOP login.

        @type username: C{str}
        @param username: The username with which to log in.

        @type password: C{str}
        @param password: The password with which to log in.

        @type challenge: C{str}
        @param challenge: A challenge string.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On a successful login, it returns the server response minus
            the status indicator.
        """
        digest = md5(challenge + password).hexdigest()
        return self.apop(username, digest)


    def apop(self, username, digest):
        """
        Send an APOP command to perform authenticated login.

        This should be used in special circumstances only, when it is
        known that the server supports APOP authentication, and APOP
        authentication is absolutely required.  For the common case,
        use L{login} instead.

        @type username: C{str}
        @param username: The username with which to log in.

        @type digest: C{str}
        @param digest: The challenge response to authenticate with.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeeds with the server
            response minus the status indicator.  On an error response, the
            deferred fails with a server error response failure.
        """
        return self.sendShort('APOP', username + ' ' + digest)


    def user(self, username):
        """
        Send a USER command to perform the first half of plaintext login.

        Unless this is absolutely required, use the L{login} method instead.

        @type username: C{str}
        @param username: The username with which to log in.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeeds with the server
            response minus the status indicator.  On an error response, the
            deferred fails with a server error response failure.
        """
        return self.sendShort('USER', username)


    def password(self, password):
        """
        Send a PASS command to perform the second half of plaintext login.

        Unless this is absolutely required, use the L{login} method instead.

        @type password: C{str}
        @param password: The plaintext password with which to authenticate.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeeds with the server
            response minus the status indicator.  On an error response, the
            deferred fails with a server error response failure.
        """
        return self.sendShort('PASS', password)


    def delete(self, index):
        """
        Send a DELE command to delete a message from the server.

        @type index: C{int}
        @param index: The 0-based index of the message to delete.

        @rtype: C{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeeds with the server
            response minus the status indicator.  On an error response, the
            deferred fails with a server error response failure.
        """
        return self.sendShort('DELE', str(index + 1))


    def _consumeOrSetItem(self, cmd, args, consumer, xform):
        """
        Send a long command and process the multi-line response into a list
        accounting for deleted messages.

        @type consumer: C{NoneType} or callable that takes C{object}
        @param consumer: None or a function that consumes the output from
            the transform function.

        @type xform: callable that takes C{str} and returns (C{int}, C{object})
            if no consumer is specified, or callable that takes
            C{str} and returns C{object} if consumer is specified, or
            C{NoneType}
        @param xform: A function that parses a line from a multi-line response
            and transforms the values into usable form for input to the
            consumer function.  If no consumer function is specified, the
            output must be a message index and corresponding value.  If no
            transform function is specified, the line is used as is.

        @rtype: L{Deferred} which fires with C{list} of C{object} or
            C{callable} that takes C{list} of C{object}
        @return: A deferred which fires when the entire response has been
            received.  When a consumer is not provided, the return value is a
            list of the value for each message or None for deleted messages.
            Otherwise, it returns the consumer itself.
        """
        if consumer is None:
            L = []
            consumer = _ListSetter(L).setitem
            return self.sendLong(cmd, args, consumer, xform).addCallback(lambda r: L)
        return self.sendLong(cmd, args, consumer, xform)

    def _consumeOrAppend(self, cmd, args, consumer, xform):
        """
        Send a long command and process the multi-line response into a list.

        @type consumer: C{NoneType} or callable that takes C{object}
        @param consumer: None or a function that consumes the output from the
            transform function.

        @type xform: C{NoneType} or callable that takes C{str} and returns
            C{object}
        @param xform: A function that transforms a line from a multi-line
            response into usable form for input to the consumer function.  If
            no transform function is specified, the line is used as is.

        @rtype: L{Deferred} which fires with C{list} of (C{int}, C{object}) or
            C{callable} that takes (C{int}, C{object})
        @return: A deferred which fires when the entire response has been
            received.  When a consumer is not provided the return value is a
            list of the transformed lines.  Otherwise, it returns the consumer
            itself.
        """
        if consumer is None:
            L = []
            consumer = L.append
            return self.sendLong(cmd, args, consumer, xform).addCallback(lambda r: L)
        return self.sendLong(cmd, args, consumer, xform)


    def capabilities(self, useCache=True):
        """
        Send a CAPA command to retrieve the capabilities supported by
        the server.

        Not all servers support this command.  If the server does not
        support this, it is treated as though it returned a successful
        response listing no capabilities.  At some future time, this may be
        changed to instead seek out information about a server's
        capabilities in some other fashion (only if it proves useful to do
        so, and only if there are servers still in use which do not support
        CAPA but which do support POP3 extensions that are useful).

        @type useCache: C{bool}
        @param useCache: A flag that determines whether previously retrieved
            results should be used if available.

        @rtype: L{Deferred} which successfully results in a
            C{dict} of C{str} -> C{NoneType} or C{list} of C{str}
        @return: A deferred which fires with a mapping of capability name to
        parameters.  For example::

            C: CAPA
            S: +OK Capability list follows
            S: TOP
            S: USER
            S: SASL CRAM-MD5 KERBEROS_V4
            S: RESP-CODES
            S: LOGIN-DELAY 900
            S: PIPELINING
            S: EXPIRE 60
            S: UIDL
            S: IMPLEMENTATION Shlemazle-Plotz-v302
            S: .

        will be lead to a result of::

            | {'TOP': None,
            |  'USER': None,
            |  'SASL': ['CRAM-MD5', 'KERBEROS_V4'],
            |  'RESP-CODES': None,
            |  'LOGIN-DELAY': ['900'],
            |  'PIPELINING': None,
            |  'EXPIRE': ['60'],
            |  'UIDL': None,
            |  'IMPLEMENTATION': ['Shlemazle-Plotz-v302']}
        """
        if useCache and self._capCache is not None:
            return defer.succeed(self._capCache)

        cache = {}
        def consume(line):
            tmp = line.split()
            if len(tmp) == 1:
                cache[tmp[0]] = None
            elif len(tmp) > 1:
                cache[tmp[0]] = tmp[1:]

        def capaNotSupported(err):
            err.trap(ServerErrorResponse)
            return None

        def gotCapabilities(result):
            self._capCache = cache
            return cache

        d = self._consumeOrAppend('CAPA', None, consume, None)
        d.addErrback(capaNotSupported).addCallback(gotCapabilities)
        return d


    def noop(self):
        """
        Send a NOOP command asking the server to do nothing but respond.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeeds with the server
            response minus the status indicator.  On an error response, the
            deferred fails with a server error response failure.
        """
        return self.sendShort("NOOP", None)


    def reset(self):
        """
        Send a RSET command to unmark any messages that have been flagged
        for deletion on the server.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeeds with the server
            response minus the status indicator.  On an error response, the
            deferred fails with a server error response failure.
        """
        return self.sendShort("RSET", None)


    def retrieve(self, index, consumer=None, lines=None):
        """
        Send a RETR or TOP command to retrieve all or part of a message from
        the server.

        @type index: C{int}
        @param index: A 0-based message index.

        @type consumer: C{NoneType} or callable that takes C{str}
        @param consumer: (optional) A function which consumes each transformed
            line from a multi-line response as it is received.

        @type lines: C{NoneType} or C{int}
        @param lines: (optional) If specified, the number of lines of the
            message to be retrieved.  Otherwise, the entire message is
            retrieved.

        @rtype: L{Deferred} which fires with C{callable} that takes
            (C{int}, C{object}) or C{list} of C{str}
        @return: A deferred which fires when the entire response has been
            received.  When a consumer is not provided the return value is a
            list of the transformed lines.  Otherwise, it returns the consumer
            itself.
        """
        idx = str(index + 1)
        if lines is None:
            return self._consumeOrAppend('RETR', idx, consumer, _dotUnquoter)

        return self._consumeOrAppend('TOP', '%s %d' % (idx, lines), consumer, _dotUnquoter)


    def stat(self):
        """
        Send a STAT command to get information about the size of the mailbox.

        @rtype: L{Deferred} which successfully fires with (C{int}, C{int}) or
            fails with L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeds with the number of
            messages in the mailbox and the size of the mailbox in octets.
            On an error response, the deferred fails with a server error
            response failure.
        """
        return self.sendShort('STAT', None).addCallback(_statXform)


    def listSize(self, consumer=None):
        """
        Send a LIST command to retrieve the sizes of all messages on the
        server.

        @type consumer: C{NoneType} or callable that takes (C{int}, C{int})
        @param consumer: (optional) A function which consumes the 0-based
            message index and message size derived from the server
            response.

        @rtype: L{Deferred} which fires C{list} of C{int} or
            callable that takes (C{int}, C{int})
        @return: A deferred which fires when the entire response has been
            received.  When a consumer is not provided the return value is a
            list of message sizes.  Otherwise, it returns the consumer itself.
        """
        return self._consumeOrSetItem('LIST', None, consumer, _listXform)


    def listUID(self, consumer=None):
        """
        Send a UIDL command to retrieve the UIDs of all messages on the server.

        @type consumer: C{NoneType} or callable that takes (C{int}, C{str})
        @param consumer: (optional) A function which consumes the 0-based
        message index and UID derived from the server response.

        @rtype: L{Deferred} which fires with C{list} of C{object} or
            C{callable} that takes (C{int}, C{str})
        @return: A deferred which fires when the entire response has been
            received.  When a consumer is not provided the return value is a
            list of message sizes.  Otherwise, it returns the consumer itself.
        """
        return self._consumeOrSetItem('UIDL', None, consumer, _uidXform)


    def quit(self):
        """
        Send a QUIT command to disconnect from the server.

        @rtype: L{Deferred} which successfully fires with C{str} or fails with
            L{ServerErrorResponse}
        @return: A deferred which fires when the server response is received.
            On an okay response, the deferred succeeds with the server
            response minus the status indicator.  On an error response, the
            deferred fails with a server error response failure.
        """
        return self.sendShort('QUIT', None)



__all__ = [
    # Exceptions
    'InsecureAuthenticationDisallowed', 'LineTooLong', 'POP3ClientError',
    'ServerErrorResponse', 'TLSError', 'TLSNotSupportedError',

    # Protocol classes
    'POP3Client']
