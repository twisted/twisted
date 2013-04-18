# -*- test-case-name: twisted.mail.test.test_pop3client -*-
# Copyright (c) 2001-2004 Divmod Inc.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
POP3 client protocol implementation

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
    """Base class for all exceptions raised by POP3Client.
    """

class InsecureAuthenticationDisallowed(POP3ClientError):
    """Secure authentication was required but no mechanism could be found.
    """

class TLSError(POP3ClientError):
    """
    Secure authentication was required but either the transport does
    not support TLS or no TLS context factory was supplied.
    """

class TLSNotSupportedError(POP3ClientError):
    """
    Secure authentication was required but the server does not support
    TLS.
    """

class ServerErrorResponse(POP3ClientError):
    """The server returned an error response to a request.
    """
    def __init__(self, reason, consumer=None):
        POP3ClientError.__init__(self, reason)
        self.consumer = consumer

class LineTooLong(POP3ClientError):
    """The server sent an extremely long line.
    """

class _ListSetter:
    # Internal helper.  POP3 responses sometimes occur in the
    # form of a list of lines containing two pieces of data,
    # a message index and a value of some sort.  When a message
    # is deleted, it is omitted from these responses.  The
    # setitem method of this class is meant to be called with
    # these two values.  In the cases where indexes are skipped,
    # it takes care of padding out the missing values with None.
    def __init__(self, L):
        self.L = L
    def setitem(self, (item, value)):
        diff = item - len(self.L) + 1
        if diff > 0:
            self.L.extend([None] * diff)
        self.L[item] = value


def _statXform(line):
    # Parse a STAT response
    numMsgs, totalSize = line.split(None, 1)
    return int(numMsgs), int(totalSize)


def _listXform(line):
    # Parse a LIST response
    index, size = line.split(None, 1)
    return int(index) - 1, int(size)


def _uidXform(line):
    # Parse a UIDL response
    index, uid = line.split(None, 1)
    return int(index) - 1, uid

def _codeStatusSplit(line):
    # Parse an +OK or -ERR response
    parts = line.split(' ', 1)
    if len(parts) == 1:
        return parts[0], ''
    return parts

def _dotUnquoter(line):
    """
    C{'.'} characters which begin a line of a message are doubled to avoid
    confusing with the terminating C{'.\\r\\n'} sequence.  This function
    unquotes them.
    """
    if line.startswith('..'):
        return line[1:]
    return line

class POP3Client(basic.LineOnlyReceiver, policies.TimeoutMixin):
    """POP3 client protocol implementation class

    Instances of this class provide a convenient, efficient API for
    retrieving and deleting messages from a POP3 server.

    @type startedTLS: C{bool}
    @ivar startedTLS: Whether TLS has been negotiated successfully.


    @type allowInsecureLogin: C{bool}
    @ivar allowInsecureLogin: Indicate whether login() should be
    allowed if the server offers no authentication challenge and if
    our transport does not offer any protection via encryption.

    @type serverChallenge: C{str} or C{None}
    @ivar serverChallenge: Challenge received from the server

    @type timeout: C{int}
    @ivar timeout: Number of seconds to wait before timing out a
    connection.  If the number is <= 0, no timeout checking will be
    performed.
    """

    startedTLS = False
    allowInsecureLogin = False
    timeout = 0
    serverChallenge = None

    # Capabilities are not allowed to change during the session
    # (except when TLS is negotiated), so cache the first response and
    # use that for all later lookups
    _capCache = None

    # Regular expression to search for in the challenge string in the server
    # greeting line.
    _challengeMagicRe = re.compile('(<[^>]+>)')

    # List of pending calls.
    # We are a pipelining API but don't actually
    # support pipelining on the network yet.
    _blockedQueue = None

    # The Deferred to which the very next result will go.
    _waiting = None

    # Whether we dropped the connection because of a timeout
    _timedOut = False

    # If the server sends an initial -ERR, this is the message it sent
    # with it.
    _greetingError = None

    def _blocked(self, f, *a):
        # Internal helper.  If commands are being blocked, append
        # the given command and arguments to a list and return a Deferred
        # that will be chained with the return value of the function
        # when it eventually runs.  Otherwise, set up for commands to be

        # blocked and return None.
        if self._blockedQueue is not None:
            d = defer.Deferred()
            self._blockedQueue.append((d, f, a))
            return d
        self._blockedQueue = []
        return None

    def _unblock(self):
        # Internal helper.  Indicate that a function has completed.
        # If there are blocked commands, run the next one.  If there
        # are not, set up for the next command to not be blocked.
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
        # Internal helper.  Send a command to which a short response
        # is expected.  Return a Deferred that fires when the response
        # is received.  Block all further commands from being sent until
        # the response is received.  Transition the state to SHORT.
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
        # Internal helper.  Send a command to which a multiline
        # response is expected.  Return a Deferred that fires when
        # the entire response is received.  Block all further commands
        # from being sent until the entire response is received.
        # Transition the state to LONG_INITIAL.
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
        if self.timeout > 0:
            self.setTimeout(self.timeout)

        self.state = 'WELCOME'
        self._blockedQueue = []

    def timeoutConnection(self):
        self._timedOut = True
        self.transport.loseConnection()

    def connectionLost(self, reason):
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
        if self.timeout > 0:
            self.resetTimeout()

        state = self.state
        self.state = None
        state = getattr(self, 'state_' + state)(line) or state
        if self.state is None:
            self.state = state

    def lineLengthExceeded(self, buffer):
        # XXX - We need to be smarter about this
        if self._waiting is not None:
            waiting, self._waiting = self._waiting, None
            waiting.errback(LineTooLong())
        self.transport.loseConnection()

    # POP3 Client state logic - don't touch this.
    def state_WELCOME(self, line):
        # WELCOME is the first state.  The server sends one line of text
        # greeting us, possibly with an APOP challenge.  Transition the
        # state to WAITING.
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
        # The server isn't supposed to send us anything in this state.
        log.msg("Illegal line from server: " + repr(line))

    def state_SHORT(self, line):
        # This is the state we are in when waiting for a single
        # line response.  Parse it and fire the appropriate callback
        # or errback.  Transition the state back to WAITING.
        deferred, self._waiting = self._waiting, None
        self._unblock()
        code, status = _codeStatusSplit(line)
        if code == OK:
            deferred.callback(status)
        else:
            deferred.errback(ServerErrorResponse(status))
        return 'WAITING'

    def state_LONG_INITIAL(self, line):
        # This is the state we are in when waiting for the first
        # line of a long response.  Parse it and transition the
        # state to LONG if it is an okay response; if it is an
        # error response, fire an errback, clean up the things
        # waiting for a long response, and transition the state
        # to WAITING.
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
        # This is the state for each line of a long response.
        # If it is the last line, finish things, fire the
        # Deferred, and transition the state to WAITING.
        # Otherwise, pass the line to the consumer.
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
        """Called when the server has sent us a greeting.

        @type greeting: C{str} or C{None}
        @param greeting: The status message sent with the server
        greeting.  For servers implementing APOP authentication, this
        will be a challenge string.  .
        """


    # External API - call these (most of 'em anyway)
    def startTLS(self, contextFactory=None):
        """
        Initiates a 'STLS' request and negotiates the TLS / SSL
        Handshake.

        @type contextFactory: C{ssl.ClientContextFactory} @param
        contextFactory: The context factory with which to negotiate
        TLS.  If C{None}, try to create a new one.

        @return: A Deferred which fires when the transport has been
        secured according to the given contextFactory, or which fails
        if the transport cannot be secured.
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
        self.transport = tls
        self.transport.startTLS(context)
        self._capCache = None
        self.startedTLS = True
        return result


    def _getContextFactory(self):
        try:
            from twisted.internet import ssl
        except ImportError:
            return None
        else:
            context = ssl.ClientContextFactory()
            context.method = ssl.SSL.TLSv1_METHOD
            return context


    def login(self, username, password):
        """Log into the server.

        If APOP is available it will be used.  Otherwise, if TLS is
        available an 'STLS' session will be started and plaintext
        login will proceed.  Otherwise, if the instance attribute
        allowInsecureLogin is set to True, insecure plaintext login
        will proceed.  Otherwise, InsecureAuthenticationDisallowed
        will be raised (asynchronously).

        @param username: The username with which to log in.
        @param password: The password with which to log in.

        @rtype: C{Deferred}
        @return: A deferred which fires when login has
        completed.
        """
        d = self.capabilities()
        d.addCallback(self._login, username, password)
        return d


    def _login(self, caps, username, password):
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
        return self._plaintext(username, password)

    def _plaintext(self, username, password):
        # Internal helper.  Send a username/password pair, returning a Deferred
        # that fires when both have succeeded or fails when the server rejects
        # either.
        return self.user(username).addCallback(lambda r: self.password(password))

    def _apop(self, username, password, challenge):
        # Internal helper.  Computes and sends an APOP response.  Returns
        # a Deferred that fires when the server responds to the response.
        digest = md5(challenge + password).hexdigest()
        return self.apop(username, digest)

    def apop(self, username, digest):
        """Perform APOP login.

        This should be used in special circumstances only, when it is
        known that the server supports APOP authentication, and APOP
        authentication is absolutely required.  For the common case,
        use L{login} instead.

        @param username: The username with which to log in.
        @param digest: The challenge response to authenticate with.
        """
        return self.sendShort('APOP', username + ' ' + digest)

    def user(self, username):
        """Send the user command.

        This performs the first half of plaintext login.  Unless this
        is absolutely required, use the L{login} method instead.

        @param username: The username with which to log in.
        """
        return self.sendShort('USER', username)

    def password(self, password):
        """Send the password command.

        This performs the second half of plaintext login.  Unless this
        is absolutely required, use the L{login} method instead.

        @param password: The plaintext password with which to authenticate.
        """
        return self.sendShort('PASS', password)

    def delete(self, index):
        """Delete a message from the server.

        @type index: C{int}
        @param index: The index of the message to delete.
        This is 0-based.

        @rtype: C{Deferred}
        @return: A deferred which fires when the delete command
        is successful, or fails if the server returns an error.
        """
        return self.sendShort('DELE', str(index + 1))

    def _consumeOrSetItem(self, cmd, args, consumer, xform):
        # Internal helper.  Send a long command.  If no consumer is
        # provided, create a consumer that puts results into a list
        # and return a Deferred that fires with that list when it
        # is complete.
        if consumer is None:
            L = []
            consumer = _ListSetter(L).setitem
            return self.sendLong(cmd, args, consumer, xform).addCallback(lambda r: L)
        return self.sendLong(cmd, args, consumer, xform)

    def _consumeOrAppend(self, cmd, args, consumer, xform):
        # Internal helper.  Send a long command.  If no consumer is
        # provided, create a consumer that appends results to a list
        # and return a Deferred that fires with that list when it is
        # complete.
        if consumer is None:
            L = []
            consumer = L.append
            return self.sendLong(cmd, args, consumer, xform).addCallback(lambda r: L)
        return self.sendLong(cmd, args, consumer, xform)

    def capabilities(self, useCache=True):
        """Retrieve the capabilities supported by this server.

        Not all servers support this command.  If the server does not
        support this, it is treated as though it returned a successful
        response listing no capabilities.  At some future time, this may be
        changed to instead seek out information about a server's
        capabilities in some other fashion (only if it proves useful to do
        so, and only if there are servers still in use which do not support
        CAPA but which do support POP3 extensions that are useful).

        @type useCache: C{bool}
        @param useCache: If set, and if capabilities have been
        retrieved previously, just return the previously retrieved
        results.

        @return: A Deferred which fires with a C{dict} mapping C{str}
        to C{None} or C{list}s of C{str}.  For example::

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
        """Do nothing, with the help of the server.

        No operation is performed.  The returned Deferred fires when
        the server responds.
        """
        return self.sendShort("NOOP", None)


    def reset(self):
        """Remove the deleted flag from any messages which have it.

        The returned Deferred fires when the server responds.
        """
        return self.sendShort("RSET", None)


    def retrieve(self, index, consumer=None, lines=None):
        """Retrieve a message from the server.

        If L{consumer} is not None, it will be called with
        each line of the message as it is received.  Otherwise,
        the returned Deferred will be fired with a list of all
        the lines when the message has been completely received.
        """
        idx = str(index + 1)
        if lines is None:
            return self._consumeOrAppend('RETR', idx, consumer, _dotUnquoter)

        return self._consumeOrAppend('TOP', '%s %d' % (idx, lines), consumer, _dotUnquoter)


    def stat(self):
        """Get information about the size of this mailbox.

        The returned Deferred will be fired with a tuple containing
        the number or messages in the mailbox and the size (in bytes)
        of the mailbox.
        """
        return self.sendShort('STAT', None).addCallback(_statXform)


    def listSize(self, consumer=None):
        """Retrieve a list of the size of all messages on the server.

        If L{consumer} is not None, it will be called with two-tuples
        of message index number and message size as they are received.
        Otherwise, a Deferred which will fire with a list of B{only}
        message sizes will be returned.  For messages which have been
        deleted, None will be used in place of the message size.
        """
        return self._consumeOrSetItem('LIST', None, consumer, _listXform)


    def listUID(self, consumer=None):
        """Retrieve a list of the UIDs of all messages on the server.

        If L{consumer} is not None, it will be called with two-tuples
        of message index number and message UID as they are received.
        Otherwise, a Deferred which will fire with of list of B{only}
        message UIDs will be returned.  For messages which have been
        deleted, None will be used in place of the message UID.
        """
        return self._consumeOrSetItem('UIDL', None, consumer, _uidXform)


    def quit(self):
        """Disconnect from the server.
        """
        return self.sendShort('QUIT', None)

__all__ = [
    # Exceptions
    'InsecureAuthenticationDisallowed', 'LineTooLong', 'POP3ClientError',
    'ServerErrorResponse', 'TLSError', 'TLSNotSupportedError',

    # Protocol classes
    'POP3Client']
