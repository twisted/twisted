# -*- test-case-name: twisted.mail.test.test_pop3client -*-
# Copyright (c) 2001-2004 Divmod Inc.
# See LICENSE for details.

"""POP3 client protocol implementation

Don't use this module directly.  Use twisted.mail.pop3 instead.

@author U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}

API Stability: Unstable
"""

import re, md5

from twisted.python import log
from twisted.internet import defer
from twisted.protocols import basic

OK = '+OK'
ERR = '-ERR'

class POP3ClientError(Exception):
    """Base class for all exceptions raised by POP3Client.
    """

class InsecureAuthenticationDisallowed(POP3ClientError):
    """Secure authentication was required but no mechanism could be found.
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
    '.' characters which begin a line of a message are doubled to avoid
    confusing with the terminating '.\r\n' sequence.  This function unquotes
    them.
    """
    if line.startswith('..'):
        return line[1:]
    return line

class POP3Client(basic.LineOnlyReceiver):
    """POP3 client protocol implementation class

    Instances of this class provide a convenient, efficient API for
    retrieving and deleting messages from a POP3 server.
    """

    # Indicate whether login() should be allowed if the server
    # offers no authentication challenge and if our transport
    # does not offer any protection via encryption.
    allowInsecureLogin = False

    # Regular expression to search for in the challenge string in the server
    # greeting line.
    challengeMagicRe = re.compile('(<[^>]+>)')

    # Challenge received from the server; set by the default
    # serverGreeting implementation.
    serverChallenge = None

    # List of pending calls.
    # We are a pipelining API but don't actually
    # support pipelining on the network yet.
    _blockedQueue = None

    # The Deferred to which the very next result will go.
    waiting = None

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
            d, f, a = self._blockedQueue.pop(0)
            d2 = f(*a)
            d2.chainDeferred(d)

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
        self.waiting = defer.Deferred()
        return self.waiting

    def sendLong(self, cmd, args, consumer, xform):
        # Internal helper.  Send a command to which a multiline
        # response is expected.  Return a Deferred that fires when
        # the entire response is received.  Block all further commands
        # from being sent until the entire response is received.
        # Transition the state to LONG_INITIAL.
        d = self._blocked(self.sendLong, cmd, args, consumer)
        if d is not None:
            return d

        if args:
            self.sendLine(cmd + ' ' + args)
        else:
            self.sendLine(cmd)
        self.state = 'LONG_INITIAL'
        self.xform = xform
        self.consumer = consumer
        self.waiting = defer.Deferred()
        return self.waiting

    # Twisted protocol callback
    def connectionMade(self):
        self.state = 'WELCOME'

    def connectionLost(self, reason):
        d = []
        if self.waiting is not None:
            d.append(self.waiting)
            self.waiting = None
        if self._blockedQueue is not None:
            d.extend([deferred for (deferred, f, a) in self._blockedQueue])
            self._blockedQueue = None
        for w in d:
            w.errback(reason)

    def lineReceived(self, line):
        state = self.state
        self.state = None
        state = getattr(self, 'state_' + state)(line) or state
        if self.state is None:
            self.state = state

    def lineLengthExceeded(self, buffer):
        # XXX - We need to be smarter about this
        if self.waiting is not None:
            waiting, self.waiting = self.waiting, None
            waiting.errback(LineTooLong())
        self.transport.loseConnection()

    # POP3 Client state logic - don't touch this.
    def state_WELCOME(self, line):
        # WELCOME is the first state.  The server sends one line of text
        # greeting us, possibly with an APOP challenge.  Transition the
        # state to WAITING.
        code, status = _codeStatusSplit(line)
        if code != OK:
            self.transport.loseConnection()
        else:
            m = self.challengeMagicRe.search(status)
            if m is not None:
                self.serverGreeting(m.group(1))
            else:
                self.serverGreeting(None)
        return 'WAITING'

    def state_WAITING(self, line):
        # The server isn't supposed to send us anything in this state.
        log.msg("Illegal line from server: " + repr(line))

    def state_SHORT(self, line):
        # This is the state we are in when waiting for a single
        # line response.  Parse it and fire the appropriate callback
        # or errback.  Transition the state back to WAITING.
        deferred, self.waiting = self.waiting, None
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
        consumer = self.consumer
        deferred = self.waiting
        self.consumer = self.waiting = self.xform = None
        self._unblock()
        deferred.errback(ServerErrorResponse(status, consumer))
        return 'WAITING'

    def state_LONG(self, line):
        # This is the state for each line of a long response.
        # If it is the last line, finish things, fire the
        # Deferred, and transition the state to WAITING.
        # Otherwise, pass the line to the consumer.
        if line == '.':
            consumer = self.consumer
            deferred = self.waiting
            self.consumer = self.waiting = self.xform = None
            self._unblock()
            deferred.callback(consumer)
            return 'WAITING'
        else:
            if self.xform is not None:
                self.consumer(self.xform(line))
            else:
                self.consumer(line)
            return 'LONG'

    # Callbacks - override these
    def serverGreeting(self, challenge):
        self.serverChallenge = challenge

    # External hooks - call these (most of 'em anyway)
    def login(self, username, password):
        """Log into the server.

        If APOP is available it will be used.  Otherwise, if
        the transport being used is SSL, plaintext login will
        proceed.  Otherwise, if the instance attribute
        allowInsecureLogin is set to True, insecure plaintext
        login will proceed.  Otherwise,
        InsecureAuthenticationDisallowed will be raised
        (asynchronously).

        @param username: The username with which to log in.
        @param password: The password with which to log in.

        @rtype: C{Deferred}
        @return: A deferred which fires when login has
        completed.
        """
        if self.serverChallenge is not None:
            return self._apop(username, password, self.serverChallenge)
        elif self.transport.getHost()[0] == 'SSL' or self.allowInsecureLogin:
            return self._plaintext(username, password)
        else:
            return defer.fail(InsecureAuthenticationDisallowed())

    def _plaintext(self, username, password):
        # Internal helper.  Send a username/password pair, returning a Deferred
        # that fires when both have succeeded or fails when the server rejects
        # either.
        return self.user(username).addCallback(lambda r: self.password(password))

    def _apop(self, username, password, challenge):
        # Internal helper.  Computes and sends an APOP response.  Returns
        # a Deferred that fires when the server responds to the response.
        digest = md5.new(challenge + password).hexdigest()
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

    def capabilities(self, consumer=None):
        """Retrieve the capabilities supported by this server.

        If L{consumer} is not None, it will be called with each
        capability string as it is received.  Otherwise, the
        returned Deferred will be fired with a list of all the
        capability strings when they have all been received.
        """
        return self._consumeOrAppend('CAPA', None, consumer, None)

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
    'ServerErrorResponse',

    # Protocol classes
    'POP3Client']
