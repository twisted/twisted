# -*- test-case-name: twisted.mail.test.test_imap -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An IMAP4 protocol implementation

@author: Jp Calderone

To do::
  Suspend idle timeout while server is processing
  Use an async message parser instead of buffering in memory
  Figure out a way to not queue multi-message client requests (Flow? A simple callback?)
  Clarify some API docs (Query, etc)
  Make APPEND recognize (again) non-existent mailboxes before accepting the literal
"""

import rfc822
import base64
import binascii
import hmac
import re
import copy
import tempfile
import string
import time
import random
import types

import email.Utils

try:
    import cStringIO as StringIO
except:
    import StringIO

from zope.interface import implements, Interface

from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import defer
from twisted.internet import error
from twisted.internet.defer import maybeDeferred
from twisted.python import log, text
from twisted.internet import interfaces

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials


# locale-independent month names to use instead of strftime's
_MONTH_NAMES = dict(zip(
        range(1, 13),
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()))


class MessageSet(object):
    """
    Essentially an infinite bitfield, with some extra features.

    @type getnext: Function taking C{int} returning C{int}
    @ivar getnext: A function that returns the next message number,
    used when iterating through the MessageSet. By default, a function
    returning the next integer is supplied, but as this can be rather
    inefficient for sparse UID iterations, it is recommended to supply
    one when messages are requested by UID.  The argument is provided
    as a hint to the implementation and may be ignored if it makes sense
    to do so (eg, if an iterator is being used that maintains its own
    state, it is guaranteed that it will not be called out-of-order).
    """
    _empty = []

    def __init__(self, start=_empty, end=_empty):
        """
        Create a new MessageSet()

        @type start: Optional C{int}
        @param start: Start of range, or only message number

        @type end: Optional C{int}
        @param end: End of range.
        """
        self._last = self._empty # Last message/UID in use
        self.ranges = [] # List of ranges included
        self.getnext = lambda x: x+1 # A function which will return the next
                                     # message id. Handy for UID requests.

        if start is self._empty:
            return

        if isinstance(start, types.ListType):
            self.ranges = start[:]
            self.clean()
        else:
            self.add(start,end)

    # Ooo.  A property.
    def last():
        def _setLast(self, value):
            if self._last is not self._empty:
                raise ValueError("last already set")

            self._last = value
            for i, (l, h) in enumerate(self.ranges):
                if l is not None:
                    break # There are no more Nones after this
                l = value
                if h is None:
                    h = value
                if l > h:
                    l, h = h, l
                self.ranges[i] = (l, h)

            self.clean()

        def _getLast(self):
            return self._last

        doc = '''
            "Highest" message number, refered to by "*".
            Must be set before attempting to use the MessageSet.
        '''
        return _getLast, _setLast, None, doc
    last = property(*last())

    def add(self, start, end=_empty):
        """
        Add another range

        @type start: C{int}
        @param start: Start of range, or only message number

        @type end: Optional C{int}
        @param end: End of range.
        """
        if end is self._empty:
            end = start

        if self._last is not self._empty:
            if start is None:
                start = self.last
            if end is None:
                end = self.last

        if start > end:
            # Try to keep in low, high order if possible
            # (But we don't know what None means, this will keep
            # None at the start of the ranges list)
            start, end = end, start

        self.ranges.append((start, end))
        self.clean()

    def __add__(self, other):
        if isinstance(other, MessageSet):
            ranges = self.ranges + other.ranges
            return MessageSet(ranges)
        else:
            res = MessageSet(self.ranges)
            try:
                res.add(*other)
            except TypeError:
                res.add(other)
            return res


    def extend(self, other):
        if isinstance(other, MessageSet):
            self.ranges.extend(other.ranges)
            self.clean()
        else:
            try:
                self.add(*other)
            except TypeError:
                self.add(other)

        return self


    def clean(self):
        """
        Clean ranges list, combining adjacent ranges
        """

        self.ranges.sort()

        oldl, oldh = None, None
        for i,(l, h) in enumerate(self.ranges):
            if l is None:
                continue
            # l is >= oldl and h is >= oldh due to sort()
            if oldl is not None and l <= oldh + 1:
                l = oldl
                h = max(oldh, h)
                self.ranges[i - 1] = None
                self.ranges[i] = (l, h)

            oldl, oldh = l, h

        self.ranges = filter(None, self.ranges)


    def __contains__(self, value):
        """
        May raise TypeError if we encounter an open-ended range
        """
        for l, h in self.ranges:
            if l is None:
                raise TypeError(
                    "Can't determine membership; last value not set")
            if l <= value <= h:
                return True

        return False


    def _iterator(self):
        for l, h in self.ranges:
            l = self.getnext(l-1)
            while l <= h:
                yield l
                l = self.getnext(l)
                if l is None:
                    break

    def __iter__(self):
        if self.ranges and self.ranges[0][0] is None:
            raise TypeError("Can't iterate; last value not set")

        return self._iterator()

    def __len__(self):
        res = 0
        for l, h in self.ranges:
            if l is None:
                if h is None:
                    res += 1
                else:
                    raise TypeError("Can't size object; last value not set")
            else:
                res += (h - l) + 1

        return res

    def __str__(self):
        p = []
        for low, high in self.ranges:
            if low == high:
                if low is None:
                    p.append('*')
                else:
                    p.append(str(low))
            elif low is None:
                p.append('%d:*' % (high,))
            else:
                p.append('%d:%d' % (low, high))
        return ','.join(p)

    def __repr__(self):
        return '<MessageSet %s>' % (str(self),)

    def __eq__(self, other):
        if isinstance(other, MessageSet):
            return self.ranges == other.ranges
        return False


class LiteralString:
    def __init__(self, size, defered):
        self.size = size
        self.data = []
        self.defer = defered

    def write(self, data):
        self.size -= len(data)
        passon = None
        if self.size > 0:
            self.data.append(data)
        else:
            if self.size:
                data, passon = data[:self.size], data[self.size:]
            else:
                passon = ''
            if data:
                self.data.append(data)
        return passon

    def callback(self, line):
        """
        Call defered with data and rest of line
        """
        self.defer.callback((''.join(self.data), line))

class LiteralFile:
    _memoryFileLimit = 1024 * 1024 * 10

    def __init__(self, size, defered):
        self.size = size
        self.defer = defered
        if size > self._memoryFileLimit:
            self.data = tempfile.TemporaryFile()
        else:
            self.data = StringIO.StringIO()

    def write(self, data):
        self.size -= len(data)
        passon = None
        if self.size > 0:
            self.data.write(data)
        else:
            if self.size:
                data, passon = data[:self.size], data[self.size:]
            else:
                passon = ''
            if data:
                self.data.write(data)
        return passon

    def callback(self, line):
        """
        Call defered with data and rest of line
        """
        self.data.seek(0,0)
        self.defer.callback((self.data, line))


class WriteBuffer:
    """Buffer up a bunch of writes before sending them all to a transport at once.
    """
    def __init__(self, transport, size=8192):
        self.bufferSize = size
        self.transport = transport
        self._length = 0
        self._writes = []

    def write(self, s):
        self._length += len(s)
        self._writes.append(s)
        if self._length > self.bufferSize:
            self.flush()

    def flush(self):
        if self._writes:
            self.transport.writeSequence(self._writes)
            self._writes = []
            self._length = 0


class Command:
    _1_RESPONSES = ('CAPABILITY', 'FLAGS', 'LIST', 'LSUB', 'STATUS', 'SEARCH', 'NAMESPACE')
    _2_RESPONSES = ('EXISTS', 'EXPUNGE', 'FETCH', 'RECENT')
    _OK_RESPONSES = ('UIDVALIDITY', 'UNSEEN', 'READ-WRITE', 'READ-ONLY', 'UIDNEXT', 'PERMANENTFLAGS')
    defer = None

    def __init__(self, command, args=None, wantResponse=(),
                 continuation=None, *contArgs, **contKw):
        self.command = command
        self.args = args
        self.wantResponse = wantResponse
        self.continuation = lambda x: continuation(x, *contArgs, **contKw)
        self.lines = []

    def format(self, tag):
        if self.args is None:
            return ' '.join((tag, self.command))
        return ' '.join((tag, self.command, self.args))

    def finish(self, lastLine, unusedCallback):
        send = []
        unuse = []
        for L in self.lines:
            names = parseNestedParens(L)
            N = len(names)
            if (N >= 1 and names[0] in self._1_RESPONSES or
                N >= 2 and names[1] in self._2_RESPONSES or
                N >= 2 and names[0] == 'OK' and isinstance(names[1], types.ListType) and names[1][0] in self._OK_RESPONSES):
                send.append(names)
            else:
                unuse.append(names)
        d, self.defer = self.defer, None
        d.callback((send, lastLine))
        if unuse:
            unusedCallback(unuse)

class LOGINCredentials(cred.credentials.UsernamePassword):
    def __init__(self):
        self.challenges = ['Password\0', 'User Name\0']
        self.responses = ['password', 'username']
        cred.credentials.UsernamePassword.__init__(self, None, None)

    def getChallenge(self):
        return self.challenges.pop()

    def setResponse(self, response):
        setattr(self, self.responses.pop(), response)

    def moreChallenges(self):
        return bool(self.challenges)

class PLAINCredentials(cred.credentials.UsernamePassword):
    def __init__(self):
        cred.credentials.UsernamePassword.__init__(self, None, None)

    def getChallenge(self):
        return ''

    def setResponse(self, response):
        parts = response.split('\0')
        if len(parts) != 3:
            raise IllegalClientResponse("Malformed Response - wrong number of parts")
        useless, self.username, self.password = parts

    def moreChallenges(self):
        return False

class IMAP4Exception(Exception):
    def __init__(self, *args):
        Exception.__init__(self, *args)

class IllegalClientResponse(IMAP4Exception): pass

class IllegalOperation(IMAP4Exception): pass

class IllegalMailboxEncoding(IMAP4Exception): pass

class IMailboxListener(Interface):
    """Interface for objects interested in mailbox events"""

    def modeChanged(writeable):
        """Indicates that the write status of a mailbox has changed.

        @type writeable: C{bool}
        @param writeable: A true value if write is now allowed, false
        otherwise.
        """

    def flagsChanged(newFlags):
        """Indicates that the flags of one or more messages have changed.

        @type newFlags: C{dict}
        @param newFlags: A mapping of message identifiers to tuples of flags
        now set on that message.
        """

    def newMessages(exists, recent):
        """Indicates that the number of messages in a mailbox has changed.

        @type exists: C{int} or C{None}
        @param exists: The total number of messages now in this mailbox.
        If the total number of messages has not changed, this should be
        C{None}.

        @type recent: C{int}
        @param recent: The number of messages now flagged \\Recent.
        If the number of recent messages has not changed, this should be
        C{None}.
        """

class IMAP4Server(basic.LineReceiver, policies.TimeoutMixin):
    """
    Protocol implementation for an IMAP4rev1 server.

    The server can be in any of four states:
        - Non-authenticated
        - Authenticated
        - Selected
        - Logout
    """
    implements(IMailboxListener)

    # Identifier for this server software
    IDENT = 'Twisted IMAP4rev1 Ready'

    # Number of seconds before idle timeout
    # Initially 1 minute.  Raised to 30 minutes after login.
    timeOut = 60

    POSTAUTH_TIMEOUT = 60 * 30

    # Whether STARTTLS has been issued successfully yet or not.
    startedTLS = False

    # Whether our transport supports TLS
    canStartTLS = False

    # Mapping of tags to commands we have received
    tags = None

    # The object which will handle logins for us
    portal = None

    # The account object for this connection
    account = None

    # Logout callback
    _onLogout = None

    # The currently selected mailbox
    mbox = None

    # Command data to be processed when literal data is received
    _pendingLiteral = None

    # Maximum length to accept for a "short" string literal
    _literalStringLimit = 4096

    # IChallengeResponse factories for AUTHENTICATE command
    challengers = None

    # Search terms the implementation of which needs to be passed both the last
    # message identifier (UID) and the last sequence id.
    _requiresLastMessageInfo = set(["OR", "NOT", "UID"])

    state = 'unauth'

    parseState = 'command'

    def __init__(self, chal = None, contextFactory = None, scheduler = None):
        if chal is None:
            chal = {}
        self.challengers = chal
        self.ctx = contextFactory
        if scheduler is None:
            scheduler = iterateInReactor
        self._scheduler = scheduler
        self._queuedAsync = []

    def capabilities(self):
        cap = {'AUTH': self.challengers.keys()}
        if self.ctx and self.canStartTLS:
            if not self.startedTLS and interfaces.ISSLTransport(self.transport, None) is None:
                cap['LOGINDISABLED'] = None
                cap['STARTTLS'] = None
        cap['NAMESPACE'] = None
        cap['IDLE'] = None
        return cap

    def connectionMade(self):
        self.tags = {}
        self.canStartTLS = interfaces.ITLSTransport(self.transport, None) is not None
        self.setTimeout(self.timeOut)
        self.sendServerGreeting()

    def connectionLost(self, reason):
        self.setTimeout(None)
        if self._onLogout:
            self._onLogout()
            self._onLogout = None

    def timeoutConnection(self):
        self.sendLine('* BYE Autologout; connection idle too long')
        self.transport.loseConnection()
        if self.mbox:
            self.mbox.removeListener(self)
            cmbx = ICloseableMailbox(self.mbox, None)
            if cmbx is not None:
                maybeDeferred(cmbx.close).addErrback(log.err)
            self.mbox = None
        self.state = 'timeout'

    def rawDataReceived(self, data):
        self.resetTimeout()
        passon = self._pendingLiteral.write(data)
        if passon is not None:
            self.setLineMode(passon)

    # Avoid processing commands while buffers are being dumped to
    # our transport
    blocked = None

    def _unblock(self):
        commands = self.blocked
        self.blocked = None
        while commands and self.blocked is None:
            self.lineReceived(commands.pop(0))
        if self.blocked is not None:
            self.blocked.extend(commands)

    def lineReceived(self, line):
        if self.blocked is not None:
            self.blocked.append(line)
            return

        self.resetTimeout()

        f = getattr(self, 'parse_' + self.parseState)
        try:
            f(line)
        except Exception, e:
            self.sendUntaggedResponse('BAD Server error: ' + str(e))
            log.err()

    def parse_command(self, line):
        args = line.split(None, 2)
        rest = None
        if len(args) == 3:
            tag, cmd, rest = args
        elif len(args) == 2:
            tag, cmd = args
        elif len(args) == 1:
            tag = args[0]
            self.sendBadResponse(tag, 'Missing command')
            return None
        else:
            self.sendBadResponse(None, 'Null command')
            return None

        cmd = cmd.upper()
        try:
            return self.dispatchCommand(tag, cmd, rest)
        except IllegalClientResponse, e:
            self.sendBadResponse(tag, 'Illegal syntax: ' + str(e))
        except IllegalOperation, e:
            self.sendNegativeResponse(tag, 'Illegal operation: ' + str(e))
        except IllegalMailboxEncoding, e:
            self.sendNegativeResponse(tag, 'Illegal mailbox name: ' + str(e))

    def parse_pending(self, line):
        d = self._pendingLiteral
        self._pendingLiteral = None
        self.parseState = 'command'
        d.callback(line)

    def dispatchCommand(self, tag, cmd, rest, uid=None):
        f = self.lookupCommand(cmd)
        if f:
            fn = f[0]
            parseargs = f[1:]
            self.__doCommand(tag, fn, [self, tag], parseargs, rest, uid)
        else:
            self.sendBadResponse(tag, 'Unsupported command')

    def lookupCommand(self, cmd):
        return getattr(self, '_'.join((self.state, cmd.upper())), None)

    def __doCommand(self, tag, handler, args, parseargs, line, uid):
        for (i, arg) in enumerate(parseargs):
            if callable(arg):
                parseargs = parseargs[i+1:]
                maybeDeferred(arg, self, line).addCallback(
                    self.__cbDispatch, tag, handler, args,
                    parseargs, uid).addErrback(self.__ebDispatch, tag)
                return
            else:
                args.append(arg)

        if line:
            # Too many arguments
            raise IllegalClientResponse("Too many arguments for command: " + repr(line))

        if uid is not None:
            handler(uid=uid, *args)
        else:
            handler(*args)

    def __cbDispatch(self, (arg, rest), tag, fn, args, parseargs, uid):
        args.append(arg)
        self.__doCommand(tag, fn, args, parseargs, rest, uid)

    def __ebDispatch(self, failure, tag):
        if failure.check(IllegalClientResponse):
            self.sendBadResponse(tag, 'Illegal syntax: ' + str(failure.value))
        elif failure.check(IllegalOperation):
            self.sendNegativeResponse(tag, 'Illegal operation: ' +
                                      str(failure.value))
        elif failure.check(IllegalMailboxEncoding):
            self.sendNegativeResponse(tag, 'Illegal mailbox name: ' +
                                      str(failure.value))
        else:
            self.sendBadResponse(tag, 'Server error: ' + str(failure.value))
            log.err(failure)

    def _stringLiteral(self, size):
        if size > self._literalStringLimit:
            raise IllegalClientResponse(
                "Literal too long! I accept at most %d octets" %
                (self._literalStringLimit,))
        d = defer.Deferred()
        self.parseState = 'pending'
        self._pendingLiteral = LiteralString(size, d)
        self.sendContinuationRequest('Ready for %d octets of text' % size)
        self.setRawMode()
        return d

    def _fileLiteral(self, size):
        d = defer.Deferred()
        self.parseState = 'pending'
        self._pendingLiteral = LiteralFile(size, d)
        self.sendContinuationRequest('Ready for %d octets of data' % size)
        self.setRawMode()
        return d

    def arg_astring(self, line):
        """
        Parse an astring from the line, return (arg, rest), possibly
        via a deferred (to handle literals)
        """
        line = line.strip()
        if not line:
            raise IllegalClientResponse("Missing argument")
        d = None
        arg, rest = None, None
        if line[0] == '"':
            try:
                spam, arg, rest = line.split('"',2)
                rest = rest[1:] # Strip space
            except ValueError:
                raise IllegalClientResponse("Unmatched quotes")
        elif line[0] == '{':
            # literal
            if line[-1] != '}':
                raise IllegalClientResponse("Malformed literal")
            try:
                size = int(line[1:-1])
            except ValueError:
                raise IllegalClientResponse("Bad literal size: " + line[1:-1])
            d = self._stringLiteral(size)
        else:
            arg = line.split(' ',1)
            if len(arg) == 1:
                arg.append('')
            arg, rest = arg
        return d or (arg, rest)

    # ATOM: Any CHAR except ( ) { % * " \ ] CTL SP (CHAR is 7bit)
    atomre = re.compile(r'(?P<atom>[^\](){%*"\\\x00-\x20\x80-\xff]+)( (?P<rest>.*$)|$)')

    def arg_atom(self, line):
        """
        Parse an atom from the line
        """
        if not line:
            raise IllegalClientResponse("Missing argument")
        m = self.atomre.match(line)
        if m:
            return m.group('atom'), m.group('rest')
        else:
            raise IllegalClientResponse("Malformed ATOM")

    def arg_plist(self, line):
        """
        Parse a (non-nested) parenthesised list from the line
        """
        if not line:
            raise IllegalClientResponse("Missing argument")

        if line[0] != "(":
            raise IllegalClientResponse("Missing parenthesis")

        i = line.find(")")

        if i == -1:
            raise IllegalClientResponse("Mismatched parenthesis")

        return (parseNestedParens(line[1:i],0), line[i+2:])

    def arg_literal(self, line):
        """
        Parse a literal from the line
        """
        if not line:
            raise IllegalClientResponse("Missing argument")

        if line[0] != '{':
            raise IllegalClientResponse("Missing literal")

        if line[-1] != '}':
            raise IllegalClientResponse("Malformed literal")

        try:
            size = int(line[1:-1])
        except ValueError:
            raise IllegalClientResponse("Bad literal size: " + line[1:-1])

        return self._fileLiteral(size)

    def arg_searchkeys(self, line):
        """
        searchkeys
        """
        query = parseNestedParens(line)
        # XXX Should really use list of search terms and parse into
        # a proper tree

        return (query, '')

    def arg_seqset(self, line):
        """
        sequence-set
        """
        rest = ''
        arg = line.split(' ',1)
        if len(arg) == 2:
            rest = arg[1]
        arg = arg[0]

        try:
            return (parseIdList(arg), rest)
        except IllegalIdentifierError, e:
            raise IllegalClientResponse("Bad message number " + str(e))

    def arg_fetchatt(self, line):
        """
        fetch-att
        """
        p = _FetchParser()
        p.parseString(line)
        return (p.result, '')

    def arg_flaglist(self, line):
        """
        Flag part of store-att-flag
        """
        flags = []
        if line[0] == '(':
            if line[-1] != ')':
                raise IllegalClientResponse("Mismatched parenthesis")
            line = line[1:-1]

        while line:
            m = self.atomre.search(line)
            if not m:
                raise IllegalClientResponse("Malformed flag")
            if line[0] == '\\' and m.start() == 1:
                flags.append('\\' + m.group('atom'))
            elif m.start() == 0:
                flags.append(m.group('atom'))
            else:
                raise IllegalClientResponse("Malformed flag")
            line = m.group('rest')

        return (flags, '')

    def arg_line(self, line):
        """
        Command line of UID command
        """
        return (line, '')

    def opt_plist(self, line):
        """
        Optional parenthesised list
        """
        if line.startswith('('):
            return self.arg_plist(line)
        else:
            return (None, line)

    def opt_datetime(self, line):
        """
        Optional date-time string
        """
        if line.startswith('"'):
            try:
                spam, date, rest = line.split('"',2)
            except IndexError:
                raise IllegalClientResponse("Malformed date-time")
            return (date, rest[1:])
        else:
            return (None, line)

    def opt_charset(self, line):
        """
        Optional charset of SEARCH command
        """
        if line[:7].upper() == 'CHARSET':
            arg = line.split(' ',2)
            if len(arg) == 1:
                raise IllegalClientResponse("Missing charset identifier")
            if len(arg) == 2:
                arg.append('')
            spam, arg, rest = arg
            return (arg, rest)
        else:
            return (None, line)

    def sendServerGreeting(self):
        msg = '[CAPABILITY %s] %s' % (' '.join(self.listCapabilities()), self.IDENT)
        self.sendPositiveResponse(message=msg)

    def sendBadResponse(self, tag = None, message = ''):
        self._respond('BAD', tag, message)

    def sendPositiveResponse(self, tag = None, message = ''):
        self._respond('OK', tag, message)

    def sendNegativeResponse(self, tag = None, message = ''):
        self._respond('NO', tag, message)

    def sendUntaggedResponse(self, message, async=False):
        if not async or (self.blocked is None):
            self._respond(message, None, None)
        else:
            self._queuedAsync.append(message)

    def sendContinuationRequest(self, msg = 'Ready for additional command text'):
        if msg:
            self.sendLine('+ ' + msg)
        else:
            self.sendLine('+')

    def _respond(self, state, tag, message):
        if state in ('OK', 'NO', 'BAD') and self._queuedAsync:
            lines = self._queuedAsync
            self._queuedAsync = []
            for msg in lines:
                self._respond(msg, None, None)
        if not tag:
            tag = '*'
        if message:
            self.sendLine(' '.join((tag, state, message)))
        else:
            self.sendLine(' '.join((tag, state)))

    def listCapabilities(self):
        caps = ['IMAP4rev1']
        for c, v in self.capabilities().iteritems():
            if v is None:
                caps.append(c)
            elif len(v):
                caps.extend([('%s=%s' % (c, cap)) for cap in v])
        return caps

    def do_CAPABILITY(self, tag):
        self.sendUntaggedResponse('CAPABILITY ' + ' '.join(self.listCapabilities()))
        self.sendPositiveResponse(tag, 'CAPABILITY completed')

    unauth_CAPABILITY = (do_CAPABILITY,)
    auth_CAPABILITY = unauth_CAPABILITY
    select_CAPABILITY = unauth_CAPABILITY
    logout_CAPABILITY = unauth_CAPABILITY

    def do_LOGOUT(self, tag):
        self.sendUntaggedResponse('BYE Nice talking to you')
        self.sendPositiveResponse(tag, 'LOGOUT successful')
        self.transport.loseConnection()

    unauth_LOGOUT = (do_LOGOUT,)
    auth_LOGOUT = unauth_LOGOUT
    select_LOGOUT = unauth_LOGOUT
    logout_LOGOUT = unauth_LOGOUT

    def do_NOOP(self, tag):
        self.sendPositiveResponse(tag, 'NOOP No operation performed')

    unauth_NOOP = (do_NOOP,)
    auth_NOOP = unauth_NOOP
    select_NOOP = unauth_NOOP
    logout_NOOP = unauth_NOOP

    def do_AUTHENTICATE(self, tag, args):
        args = args.upper().strip()
        if args not in self.challengers:
            self.sendNegativeResponse(tag, 'AUTHENTICATE method unsupported')
        else:
            self.authenticate(self.challengers[args](), tag)

    unauth_AUTHENTICATE = (do_AUTHENTICATE, arg_atom)

    def authenticate(self, chal, tag):
        if self.portal is None:
            self.sendNegativeResponse(tag, 'Temporary authentication failure')
            return

        self._setupChallenge(chal, tag)

    def _setupChallenge(self, chal, tag):
        try:
            challenge = chal.getChallenge()
        except Exception, e:
            self.sendBadResponse(tag, 'Server error: ' + str(e))
        else:
            coded = base64.encodestring(challenge)[:-1]
            self.parseState = 'pending'
            self._pendingLiteral = defer.Deferred()
            self.sendContinuationRequest(coded)
            self._pendingLiteral.addCallback(self.__cbAuthChunk, chal, tag)
            self._pendingLiteral.addErrback(self.__ebAuthChunk, tag)

    def __cbAuthChunk(self, result, chal, tag):
        try:
            uncoded = base64.decodestring(result)
        except binascii.Error:
            raise IllegalClientResponse("Malformed Response - not base64")

        chal.setResponse(uncoded)
        if chal.moreChallenges():
            self._setupChallenge(chal, tag)
        else:
            self.portal.login(chal, None, IAccount).addCallbacks(
                self.__cbAuthResp,
                self.__ebAuthResp,
                (tag,), None, (tag,), None
            )

    def __cbAuthResp(self, (iface, avatar, logout), tag):
        assert iface is IAccount, "IAccount is the only supported interface"
        self.account = avatar
        self.state = 'auth'
        self._onLogout = logout
        self.sendPositiveResponse(tag, 'Authentication successful')
        self.setTimeout(self.POSTAUTH_TIMEOUT)

    def __ebAuthResp(self, failure, tag):
        if failure.check(cred.error.UnauthorizedLogin):
            self.sendNegativeResponse(tag, 'Authentication failed: unauthorized')
        elif failure.check(cred.error.UnhandledCredentials):
            self.sendNegativeResponse(tag, 'Authentication failed: server misconfigured')
        else:
            self.sendBadResponse(tag, 'Server error: login failed unexpectedly')
            log.err(failure)

    def __ebAuthChunk(self, failure, tag):
        self.sendNegativeResponse(tag, 'Authentication failed: ' + str(failure.value))

    def do_STARTTLS(self, tag):
        if self.startedTLS:
            self.sendNegativeResponse(tag, 'TLS already negotiated')
        elif self.ctx and self.canStartTLS:
            self.sendPositiveResponse(tag, 'Begin TLS negotiation now')
            self.transport.startTLS(self.ctx)
            self.startedTLS = True
            self.challengers = self.challengers.copy()
            if 'LOGIN' not in self.challengers:
                self.challengers['LOGIN'] = LOGINCredentials
            if 'PLAIN' not in self.challengers:
                self.challengers['PLAIN'] = PLAINCredentials
        else:
            self.sendNegativeResponse(tag, 'TLS not available')

    unauth_STARTTLS = (do_STARTTLS,)

    def do_LOGIN(self, tag, user, passwd):
        if 'LOGINDISABLED' in self.capabilities():
            self.sendBadResponse(tag, 'LOGIN is disabled before STARTTLS')
            return

        maybeDeferred(self.authenticateLogin, user, passwd
            ).addCallback(self.__cbLogin, tag
            ).addErrback(self.__ebLogin, tag
            )

    unauth_LOGIN = (do_LOGIN, arg_astring, arg_astring)

    def authenticateLogin(self, user, passwd):
        """Lookup the account associated with the given parameters

        Override this method to define the desired authentication behavior.

        The default behavior is to defer authentication to C{self.portal}
        if it is not None, or to deny the login otherwise.

        @type user: C{str}
        @param user: The username to lookup

        @type passwd: C{str}
        @param passwd: The password to login with
        """
        if self.portal:
            return self.portal.login(
                cred.credentials.UsernamePassword(user, passwd),
                None, IAccount
            )
        raise cred.error.UnauthorizedLogin()

    def __cbLogin(self, (iface, avatar, logout), tag):
        if iface is not IAccount:
            self.sendBadResponse(tag, 'Server error: login returned unexpected value')
            log.err("__cbLogin called with %r, IAccount expected" % (iface,))
        else:
            self.account = avatar
            self._onLogout = logout
            self.sendPositiveResponse(tag, 'LOGIN succeeded')
            self.state = 'auth'
            self.setTimeout(self.POSTAUTH_TIMEOUT)

    def __ebLogin(self, failure, tag):
        if failure.check(cred.error.UnauthorizedLogin):
            self.sendNegativeResponse(tag, 'LOGIN failed')
        else:
            self.sendBadResponse(tag, 'Server error: ' + str(failure.value))
            log.err(failure)

    def do_NAMESPACE(self, tag):
        personal = public = shared = None
        np = INamespacePresenter(self.account, None)
        if np is not None:
            personal = np.getPersonalNamespaces()
            public = np.getSharedNamespaces()
            shared = np.getSharedNamespaces()
        self.sendUntaggedResponse('NAMESPACE ' + collapseNestedLists([personal, public, shared]))
        self.sendPositiveResponse(tag, "NAMESPACE command completed")

    auth_NAMESPACE = (do_NAMESPACE,)
    select_NAMESPACE = auth_NAMESPACE

    def _parseMbox(self, name):
        if isinstance(name, unicode):
            return name
        try:
            return name.decode('imap4-utf-7')
        except:
            log.err()
            raise IllegalMailboxEncoding(name)

    def _selectWork(self, tag, name, rw, cmdName):
        if self.mbox:
            self.mbox.removeListener(self)
            cmbx = ICloseableMailbox(self.mbox, None)
            if cmbx is not None:
                maybeDeferred(cmbx.close).addErrback(log.err)
            self.mbox = None
            self.state = 'auth'

        name = self._parseMbox(name)
        maybeDeferred(self.account.select, self._parseMbox(name), rw
            ).addCallback(self._cbSelectWork, cmdName, tag
            ).addErrback(self._ebSelectWork, cmdName, tag
            )

    def _ebSelectWork(self, failure, cmdName, tag):
        self.sendBadResponse(tag, "%s failed: Server error" % (cmdName,))
        log.err(failure)

    def _cbSelectWork(self, mbox, cmdName, tag):
        if mbox is None:
            self.sendNegativeResponse(tag, 'No such mailbox')
            return
        if '\\noselect' in [s.lower() for s in mbox.getFlags()]:
            self.sendNegativeResponse(tag, 'Mailbox cannot be selected')
            return

        flags = mbox.getFlags()
        self.sendUntaggedResponse(str(mbox.getMessageCount()) + ' EXISTS')
        self.sendUntaggedResponse(str(mbox.getRecentCount()) + ' RECENT')
        self.sendUntaggedResponse('FLAGS (%s)' % ' '.join(flags))
        self.sendPositiveResponse(None, '[UIDVALIDITY %d]' % mbox.getUIDValidity())

        s = mbox.isWriteable() and 'READ-WRITE' or 'READ-ONLY'
        mbox.addListener(self)
        self.sendPositiveResponse(tag, '[%s] %s successful' % (s, cmdName))
        self.state = 'select'
        self.mbox = mbox

    auth_SELECT = ( _selectWork, arg_astring, 1, 'SELECT' )
    select_SELECT = auth_SELECT

    auth_EXAMINE = ( _selectWork, arg_astring, 0, 'EXAMINE' )
    select_EXAMINE = auth_EXAMINE


    def do_IDLE(self, tag):
        self.sendContinuationRequest(None)
        self.parseTag = tag
        self.lastState = self.parseState
        self.parseState = 'idle'

    def parse_idle(self, *args):
        self.parseState = self.lastState
        del self.lastState
        self.sendPositiveResponse(self.parseTag, "IDLE terminated")
        del self.parseTag

    select_IDLE = ( do_IDLE, )
    auth_IDLE = select_IDLE


    def do_CREATE(self, tag, name):
        name = self._parseMbox(name)
        try:
            result = self.account.create(name)
        except MailboxException, c:
            self.sendNegativeResponse(tag, str(c))
        except:
            self.sendBadResponse(tag, "Server error encountered while creating mailbox")
            log.err()
        else:
            if result:
                self.sendPositiveResponse(tag, 'Mailbox created')
            else:
                self.sendNegativeResponse(tag, 'Mailbox not created')

    auth_CREATE = (do_CREATE, arg_astring)
    select_CREATE = auth_CREATE

    def do_DELETE(self, tag, name):
        name = self._parseMbox(name)
        if name.lower() == 'inbox':
            self.sendNegativeResponse(tag, 'You cannot delete the inbox')
            return
        try:
            self.account.delete(name)
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        except:
            self.sendBadResponse(tag, "Server error encountered while deleting mailbox")
            log.err()
        else:
            self.sendPositiveResponse(tag, 'Mailbox deleted')

    auth_DELETE = (do_DELETE, arg_astring)
    select_DELETE = auth_DELETE

    def do_RENAME(self, tag, oldname, newname):
        oldname, newname = [self._parseMbox(n) for n in oldname, newname]
        if oldname.lower() == 'inbox' or newname.lower() == 'inbox':
            self.sendNegativeResponse(tag, 'You cannot rename the inbox, or rename another mailbox to inbox.')
            return
        try:
            self.account.rename(oldname, newname)
        except TypeError:
            self.sendBadResponse(tag, 'Invalid command syntax')
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        except:
            self.sendBadResponse(tag, "Server error encountered while renaming mailbox")
            log.err()
        else:
            self.sendPositiveResponse(tag, 'Mailbox renamed')

    auth_RENAME = (do_RENAME, arg_astring, arg_astring)
    select_RENAME = auth_RENAME

    def do_SUBSCRIBE(self, tag, name):
        name = self._parseMbox(name)
        try:
            self.account.subscribe(name)
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        except:
            self.sendBadResponse(tag, "Server error encountered while subscribing to mailbox")
            log.err()
        else:
            self.sendPositiveResponse(tag, 'Subscribed')

    auth_SUBSCRIBE = (do_SUBSCRIBE, arg_astring)
    select_SUBSCRIBE = auth_SUBSCRIBE

    def do_UNSUBSCRIBE(self, tag, name):
        name = self._parseMbox(name)
        try:
            self.account.unsubscribe(name)
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        except:
            self.sendBadResponse(tag, "Server error encountered while unsubscribing from mailbox")
            log.err()
        else:
            self.sendPositiveResponse(tag, 'Unsubscribed')

    auth_UNSUBSCRIBE = (do_UNSUBSCRIBE, arg_astring)
    select_UNSUBSCRIBE = auth_UNSUBSCRIBE

    def _listWork(self, tag, ref, mbox, sub, cmdName):
        mbox = self._parseMbox(mbox)
        maybeDeferred(self.account.listMailboxes, ref, mbox
            ).addCallback(self._cbListWork, tag, sub, cmdName
            ).addErrback(self._ebListWork, tag
            )

    def _cbListWork(self, mailboxes, tag, sub, cmdName):
        for (name, box) in mailboxes:
            if not sub or self.account.isSubscribed(name):
                flags = box.getFlags()
                delim = box.getHierarchicalDelimiter()
                resp = (DontQuoteMe(cmdName), map(DontQuoteMe, flags), delim, name.encode('imap4-utf-7'))
                self.sendUntaggedResponse(collapseNestedLists(resp))
        self.sendPositiveResponse(tag, '%s completed' % (cmdName,))

    def _ebListWork(self, failure, tag):
        self.sendBadResponse(tag, "Server error encountered while listing mailboxes.")
        log.err(failure)

    auth_LIST = (_listWork, arg_astring, arg_astring, 0, 'LIST')
    select_LIST = auth_LIST

    auth_LSUB = (_listWork, arg_astring, arg_astring, 1, 'LSUB')
    select_LSUB = auth_LSUB

    def do_STATUS(self, tag, mailbox, names):
        mailbox = self._parseMbox(mailbox)
        maybeDeferred(self.account.select, mailbox, 0
            ).addCallback(self._cbStatusGotMailbox, tag, mailbox, names
            ).addErrback(self._ebStatusGotMailbox, tag
            )

    def _cbStatusGotMailbox(self, mbox, tag, mailbox, names):
        if mbox:
            maybeDeferred(mbox.requestStatus, names).addCallbacks(
                self.__cbStatus, self.__ebStatus,
                (tag, mailbox), None, (tag, mailbox), None
            )
        else:
            self.sendNegativeResponse(tag, "Could not open mailbox")

    def _ebStatusGotMailbox(self, failure, tag):
        self.sendBadResponse(tag, "Server error encountered while opening mailbox.")
        log.err(failure)

    auth_STATUS = (do_STATUS, arg_astring, arg_plist)
    select_STATUS = auth_STATUS

    def __cbStatus(self, status, tag, box):
        line = ' '.join(['%s %s' % x for x in status.iteritems()])
        self.sendUntaggedResponse('STATUS %s (%s)' % (box, line))
        self.sendPositiveResponse(tag, 'STATUS complete')

    def __ebStatus(self, failure, tag, box):
        self.sendBadResponse(tag, 'STATUS %s failed: %s' % (box, str(failure.value)))

    def do_APPEND(self, tag, mailbox, flags, date, message):
        mailbox = self._parseMbox(mailbox)
        maybeDeferred(self.account.select, mailbox
            ).addCallback(self._cbAppendGotMailbox, tag, flags, date, message
            ).addErrback(self._ebAppendGotMailbox, tag
            )

    def _cbAppendGotMailbox(self, mbox, tag, flags, date, message):
        if not mbox:
            self.sendNegativeResponse(tag, '[TRYCREATE] No such mailbox')
            return

        d = mbox.addMessage(message, flags, date)
        d.addCallback(self.__cbAppend, tag, mbox)
        d.addErrback(self.__ebAppend, tag)

    def _ebAppendGotMailbox(self, failure, tag):
        self.sendBadResponse(tag, "Server error encountered while opening mailbox.")
        log.err(failure)

    auth_APPEND = (do_APPEND, arg_astring, opt_plist, opt_datetime,
                   arg_literal)
    select_APPEND = auth_APPEND

    def __cbAppend(self, result, tag, mbox):
        self.sendUntaggedResponse('%d EXISTS' % mbox.getMessageCount())
        self.sendPositiveResponse(tag, 'APPEND complete')

    def __ebAppend(self, failure, tag):
        self.sendBadResponse(tag, 'APPEND failed: ' + str(failure.value))

    def do_CHECK(self, tag):
        d = self.checkpoint()
        if d is None:
            self.__cbCheck(None, tag)
        else:
            d.addCallbacks(
                self.__cbCheck,
                self.__ebCheck,
                callbackArgs=(tag,),
                errbackArgs=(tag,)
            )
    select_CHECK = (do_CHECK,)

    def __cbCheck(self, result, tag):
        self.sendPositiveResponse(tag, 'CHECK completed')

    def __ebCheck(self, failure, tag):
        self.sendBadResponse(tag, 'CHECK failed: ' + str(failure.value))

    def checkpoint(self):
        """Called when the client issues a CHECK command.

        This should perform any checkpoint operations required by the server.
        It may be a long running operation, but may not block.  If it returns
        a deferred, the client will only be informed of success (or failure)
        when the deferred's callback (or errback) is invoked.
        """
        return None

    def do_CLOSE(self, tag):
        d = None
        if self.mbox.isWriteable():
            d = maybeDeferred(self.mbox.expunge)
        cmbx = ICloseableMailbox(self.mbox, None)
        if cmbx is not None:
            if d is not None:
                d.addCallback(lambda result: cmbx.close())
            else:
                d = maybeDeferred(cmbx.close)
        if d is not None:
            d.addCallbacks(self.__cbClose, self.__ebClose, (tag,), None, (tag,), None)
        else:
            self.__cbClose(None, tag)

    select_CLOSE = (do_CLOSE,)

    def __cbClose(self, result, tag):
        self.sendPositiveResponse(tag, 'CLOSE completed')
        self.mbox.removeListener(self)
        self.mbox = None
        self.state = 'auth'

    def __ebClose(self, failure, tag):
        self.sendBadResponse(tag, 'CLOSE failed: ' + str(failure.value))

    def do_EXPUNGE(self, tag):
        if self.mbox.isWriteable():
            maybeDeferred(self.mbox.expunge).addCallbacks(
                self.__cbExpunge, self.__ebExpunge, (tag,), None, (tag,), None
            )
        else:
            self.sendNegativeResponse(tag, 'EXPUNGE ignored on read-only mailbox')

    select_EXPUNGE = (do_EXPUNGE,)

    def __cbExpunge(self, result, tag):
        for e in result:
            self.sendUntaggedResponse('%d EXPUNGE' % e)
        self.sendPositiveResponse(tag, 'EXPUNGE completed')

    def __ebExpunge(self, failure, tag):
        self.sendBadResponse(tag, 'EXPUNGE failed: ' + str(failure.value))
        log.err(failure)

    def do_SEARCH(self, tag, charset, query, uid=0):
        sm = ISearchableMailbox(self.mbox, None)
        if sm is not None:
            maybeDeferred(sm.search, query, uid=uid
                          ).addCallback(self.__cbSearch, tag, self.mbox, uid
                          ).addErrback(self.__ebSearch, tag)
        else:
            # that's not the ideal way to get all messages, there should be a
            # method on mailboxes that gives you all of them
            s = parseIdList('1:*')
            maybeDeferred(self.mbox.fetch, s, uid=uid
                          ).addCallback(self.__cbManualSearch,
                                        tag, self.mbox, query, uid
                          ).addErrback(self.__ebSearch, tag)


    select_SEARCH = (do_SEARCH, opt_charset, arg_searchkeys)

    def __cbSearch(self, result, tag, mbox, uid):
        if uid:
            result = map(mbox.getUID, result)
        ids = ' '.join([str(i) for i in result])
        self.sendUntaggedResponse('SEARCH ' + ids)
        self.sendPositiveResponse(tag, 'SEARCH completed')


    def __cbManualSearch(self, result, tag, mbox, query, uid,
                         searchResults=None):
        """
        Apply the search filter to a set of messages. Send the response to the
        client.

        @type result: C{list} of C{tuple} of (C{int}, provider of
            L{imap4.IMessage})
        @param result: A list two tuples of messages with their sequence ids,
            sorted by the ids in descending order.

        @type tag: C{str}
        @param tag: A command tag.

        @type mbox: Provider of L{imap4.IMailbox}
        @param mbox: The searched mailbox.

        @type query: C{list}
        @param query: A list representing the parsed form of the search query.

        @param uid: A flag indicating whether the search is over message
            sequence numbers or UIDs.

        @type searchResults: C{list}
        @param searchResults: The search results so far or C{None} if no
            results yet.
        """
        if searchResults is None:
            searchResults = []
        i = 0

        # result is a list of tuples (sequenceId, Message)
        lastSequenceId = result and result[-1][0]
        lastMessageId = result and result[-1][1].getUID()

        for (i, (id, msg)) in zip(range(5), result):
            # searchFilter and singleSearchStep will mutate the query.  Dang.
            # Copy it here or else things will go poorly for subsequent
            # messages.
            if self._searchFilter(copy.deepcopy(query), id, msg,
                                  lastSequenceId, lastMessageId):
                if uid:
                    searchResults.append(str(msg.getUID()))
                else:
                    searchResults.append(str(id))
        if i == 4:
            from twisted.internet import reactor
            reactor.callLater(
                0, self.__cbManualSearch, result[5:], tag, mbox, query, uid,
                searchResults)
        else:
            if searchResults:
                self.sendUntaggedResponse('SEARCH ' + ' '.join(searchResults))
            self.sendPositiveResponse(tag, 'SEARCH completed')


    def _searchFilter(self, query, id, msg, lastSequenceId, lastMessageId):
        """
        Pop search terms from the beginning of C{query} until there are none
        left and apply them to the given message.

        @param query: A list representing the parsed form of the search query.

        @param id: The sequence number of the message being checked.

        @param msg: The message being checked.

        @type lastSequenceId: C{int}
        @param lastSequenceId: The highest sequence number of any message in
            the mailbox being searched.

        @type lastMessageId: C{int}
        @param lastMessageId: The highest UID of any message in the mailbox
            being searched.

        @return: Boolean indicating whether all of the query terms match the
            message.
        """
        while query:
            if not self._singleSearchStep(query, id, msg,
                                          lastSequenceId, lastMessageId):
                return False
        return True


    def _singleSearchStep(self, query, id, msg, lastSequenceId, lastMessageId):
        """
        Pop one search term from the beginning of C{query} (possibly more than
        one element) and return whether it matches the given message.

        @param query: A list representing the parsed form of the search query.

        @param id: The sequence number of the message being checked.

        @param msg: The message being checked.

        @param lastSequenceId: The highest sequence number of any message in
            the mailbox being searched.

        @param lastMessageId: The highest UID of any message in the mailbox
            being searched.

        @return: Boolean indicating whether the query term matched the message.
        """

        q = query.pop(0)
        if isinstance(q, list):
            if not self._searchFilter(q, id, msg,
                                      lastSequenceId, lastMessageId):
                return False
        else:
            c = q.upper()
            if not c[:1].isalpha():
                # A search term may be a word like ALL, ANSWERED, BCC, etc (see
                # below) or it may be a message sequence set.  Here we
                # recognize a message sequence set "N:M".
                messageSet = parseIdList(c, lastSequenceId)
                return id in messageSet
            else:
                f = getattr(self, 'search_' + c, None)
                if f is None:
                    raise IllegalQueryError("Invalid search command %s" % c)

                if c in self._requiresLastMessageInfo:
                    result = f(query, id, msg, (lastSequenceId,
                                                lastMessageId))
                else:
                    result = f(query, id, msg)

                if not result:
                    return False
        return True

    def search_ALL(self, query, id, msg):
        """
        Returns C{True} if the message matches the ALL search key (always).

        @type query: A C{list} of C{str}
        @param query: A list representing the parsed query string.

        @type id: C{int}
        @param id: The sequence number of the message being checked.

        @type msg: Provider of L{imap4.IMessage}
        """
        return True

    def search_ANSWERED(self, query, id, msg):
        """
        Returns C{True} if the message has been answered.

        @type query: A C{list} of C{str}
        @param query: A list representing the parsed query string.

        @type id: C{int}
        @param id: The sequence number of the message being checked.

        @type msg: Provider of L{imap4.IMessage}
        """
        return '\\Answered' in msg.getFlags()

    def search_BCC(self, query, id, msg):
        """
        Returns C{True} if the message has a BCC address matching the query.

        @type query: A C{list} of C{str}
        @param query: A list whose first element is a BCC C{str}

        @type id: C{int}
        @param id: The sequence number of the message being checked.

        @type msg: Provider of L{imap4.IMessage}
        """
        bcc = msg.getHeaders(False, 'bcc').get('bcc', '')
        return bcc.lower().find(query.pop(0).lower()) != -1

    def search_BEFORE(self, query, id, msg):
        date = parseTime(query.pop(0))
        return rfc822.parsedate(msg.getInternalDate()) < date

    def search_BODY(self, query, id, msg):
        body = query.pop(0).lower()
        return text.strFile(body, msg.getBodyFile(), False)

    def search_CC(self, query, id, msg):
        cc = msg.getHeaders(False, 'cc').get('cc', '')
        return cc.lower().find(query.pop(0).lower()) != -1

    def search_DELETED(self, query, id, msg):
        return '\\Deleted' in msg.getFlags()

    def search_DRAFT(self, query, id, msg):
        return '\\Draft' in msg.getFlags()

    def search_FLAGGED(self, query, id, msg):
        return '\\Flagged' in msg.getFlags()

    def search_FROM(self, query, id, msg):
        fm = msg.getHeaders(False, 'from').get('from', '')
        return fm.lower().find(query.pop(0).lower()) != -1

    def search_HEADER(self, query, id, msg):
        hdr = query.pop(0).lower()
        hdr = msg.getHeaders(False, hdr).get(hdr, '')
        return hdr.lower().find(query.pop(0).lower()) != -1

    def search_KEYWORD(self, query, id, msg):
        query.pop(0)
        return False

    def search_LARGER(self, query, id, msg):
        return int(query.pop(0)) < msg.getSize()

    def search_NEW(self, query, id, msg):
        return '\\Recent' in msg.getFlags() and '\\Seen' not in msg.getFlags()

    def search_NOT(self, query, id, msg, (lastSequenceId, lastMessageId)):
        """
        Returns C{True} if the message does not match the query.

        @type query: A C{list} of C{str}
        @param query: A list representing the parsed form of the search query.

        @type id: C{int}
        @param id: The sequence number of the message being checked.

        @type msg: Provider of L{imap4.IMessage}
        @param msg: The message being checked.

        @type lastSequenceId: C{int}
        @param lastSequenceId: The highest sequence number of a message in the
            mailbox.

        @type lastMessageId: C{int}
        @param lastMessageId: The highest UID of a message in the mailbox.
        """
        return not self._singleSearchStep(query, id, msg,
                                          lastSequenceId, lastMessageId)

    def search_OLD(self, query, id, msg):
        return '\\Recent' not in msg.getFlags()

    def search_ON(self, query, id, msg):
        date = parseTime(query.pop(0))
        return rfc822.parsedate(msg.getInternalDate()) == date

    def search_OR(self, query, id, msg, (lastSequenceId, lastMessageId)):
        """
        Returns C{True} if the message matches any of the first two query
        items.

        @type query: A C{list} of C{str}
        @param query: A list representing the parsed form of the search query.

        @type id: C{int}
        @param id: The sequence number of the message being checked.

        @type msg: Provider of L{imap4.IMessage}
        @param msg: The message being checked.

        @type lastSequenceId: C{int}
        @param lastSequenceId: The highest sequence number of a message in the
                               mailbox.

        @type lastMessageId: C{int}
        @param lastMessageId: The highest UID of a message in the mailbox.
        """
        a = self._singleSearchStep(query, id, msg,
                                   lastSequenceId, lastMessageId)
        b = self._singleSearchStep(query, id, msg,
                                   lastSequenceId, lastMessageId)
        return a or b

    def search_RECENT(self, query, id, msg):
        return '\\Recent' in msg.getFlags()

    def search_SEEN(self, query, id, msg):
        return '\\Seen' in msg.getFlags()

    def search_SENTBEFORE(self, query, id, msg):
        """
        Returns C{True} if the message date is earlier than the query date.

        @type query: A C{list} of C{str}
        @param query: A list whose first element starts with a stringified date
            that is a fragment of an L{imap4.Query()}. The date must be in the
            format 'DD-Mon-YYYY', for example '03-March-2003' or '03-Mar-2003'.

        @type id: C{int}
        @param id: The sequence number of the message being checked.

        @type msg: Provider of L{imap4.IMessage}
        """
        date = msg.getHeaders(False, 'date').get('date', '')
        date = rfc822.parsedate(date)
        return date < parseTime(query.pop(0))

    def search_SENTON(self, query, id, msg):
        """
        Returns C{True} if the message date is the same as the query date.

        @type query: A C{list} of C{str}
        @param query: A list whose first element starts with a stringified date
            that is a fragment of an L{imap4.Query()}. The date must be in the
            format 'DD-Mon-YYYY', for example '03-March-2003' or '03-Mar-2003'.

        @type msg: Provider of L{imap4.IMessage}
        """
        date = msg.getHeaders(False, 'date').get('date', '')
        date = rfc822.parsedate(date)
        return date[:3] == parseTime(query.pop(0))[:3]

    def search_SENTSINCE(self, query, id, msg):
        """
        Returns C{True} if the message date is later than the query date.

        @type query: A C{list} of C{str}
        @param query: A list whose first element starts with a stringified date
            that is a fragment of an L{imap4.Query()}. The date must be in the
            format 'DD-Mon-YYYY', for example '03-March-2003' or '03-Mar-2003'.

        @type msg: Provider of L{imap4.IMessage}
        """
        date = msg.getHeaders(False, 'date').get('date', '')
        date = rfc822.parsedate(date)
        return date > parseTime(query.pop(0))

    def search_SINCE(self, query, id, msg):
        date = parseTime(query.pop(0))
        return rfc822.parsedate(msg.getInternalDate()) > date

    def search_SMALLER(self, query, id, msg):
        return int(query.pop(0)) > msg.getSize()

    def search_SUBJECT(self, query, id, msg):
        subj = msg.getHeaders(False, 'subject').get('subject', '')
        return subj.lower().find(query.pop(0).lower()) != -1

    def search_TEXT(self, query, id, msg):
        # XXX - This must search headers too
        body = query.pop(0).lower()
        return text.strFile(body, msg.getBodyFile(), False)

    def search_TO(self, query, id, msg):
        to = msg.getHeaders(False, 'to').get('to', '')
        return to.lower().find(query.pop(0).lower()) != -1

    def search_UID(self, query, id, msg, (lastSequenceId, lastMessageId)):
        """
        Returns C{True} if the message UID is in the range defined by the
        search query.

        @type query: A C{list} of C{str}
        @param query: A list representing the parsed form of the search
            query. Its first element should be a C{str} that can be interpreted
            as a sequence range, for example '2:4,5:*'.

        @type id: C{int}
        @param id: The sequence number of the message being checked.

        @type msg: Provider of L{imap4.IMessage}
        @param msg: The message being checked.

        @type lastSequenceId: C{int}
        @param lastSequenceId: The highest sequence number of a message in the
            mailbox.

        @type lastMessageId: C{int}
        @param lastMessageId: The highest UID of a message in the mailbox.
        """
        c = query.pop(0)
        m = parseIdList(c, lastMessageId)
        return msg.getUID() in m

    def search_UNANSWERED(self, query, id, msg):
        return '\\Answered' not in msg.getFlags()

    def search_UNDELETED(self, query, id, msg):
        return '\\Deleted' not in msg.getFlags()

    def search_UNDRAFT(self, query, id, msg):
        return '\\Draft' not in msg.getFlags()

    def search_UNFLAGGED(self, query, id, msg):
        return '\\Flagged' not in msg.getFlags()

    def search_UNKEYWORD(self, query, id, msg):
        query.pop(0)
        return False

    def search_UNSEEN(self, query, id, msg):
        return '\\Seen' not in msg.getFlags()

    def __ebSearch(self, failure, tag):
        self.sendBadResponse(tag, 'SEARCH failed: ' + str(failure.value))
        log.err(failure)

    def do_FETCH(self, tag, messages, query, uid=0):
        if query:
            self._oldTimeout = self.setTimeout(None)
            maybeDeferred(self.mbox.fetch, messages, uid=uid
                ).addCallback(iter
                ).addCallback(self.__cbFetch, tag, query, uid
                ).addErrback(self.__ebFetch, tag
                )
        else:
            self.sendPositiveResponse(tag, 'FETCH complete')

    select_FETCH = (do_FETCH, arg_seqset, arg_fetchatt)

    def __cbFetch(self, results, tag, query, uid):
        if self.blocked is None:
            self.blocked = []
        try:
            id, msg = results.next()
        except StopIteration:
            # The idle timeout was suspended while we delivered results,
            # restore it now.
            self.setTimeout(self._oldTimeout)
            del self._oldTimeout

            # All results have been processed, deliver completion notification.

            # It's important to run this *after* resetting the timeout to "rig
            # a race" in some test code. writing to the transport will
            # synchronously call test code, which synchronously loses the
            # connection, calling our connectionLost method, which cancels the
            # timeout. We want to make sure that timeout is cancelled *after*
            # we reset it above, so that the final state is no timed
            # calls. This avoids reactor uncleanliness errors in the test
            # suite.
            # XXX: Perhaps loopback should be fixed to not call the user code
            # synchronously in transport.write?
            self.sendPositiveResponse(tag, 'FETCH completed')

            # Instance state is now consistent again (ie, it is as though
            # the fetch command never ran), so allow any pending blocked
            # commands to execute.
            self._unblock()
        else:
            self.spewMessage(id, msg, query, uid
                ).addCallback(lambda _: self.__cbFetch(results, tag, query, uid)
                ).addErrback(self.__ebSpewMessage
                )

    def __ebSpewMessage(self, failure):
        # This indicates a programming error.
        # There's no reliable way to indicate anything to the client, since we
        # may have already written an arbitrary amount of data in response to
        # the command.
        log.err(failure)
        self.transport.loseConnection()

    def spew_envelope(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        _w('ENVELOPE ' + collapseNestedLists([getEnvelope(msg)]))

    def spew_flags(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        _w('FLAGS ' + '(%s)' % (' '.join(msg.getFlags())))

    def spew_internaldate(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        idate = msg.getInternalDate()
        ttup = rfc822.parsedate_tz(idate)
        if ttup is None:
            log.msg("%d:%r: unpareseable internaldate: %r" % (id, msg, idate))
            raise IMAP4Exception("Internal failure generating INTERNALDATE")

        # need to specify the month manually, as strftime depends on locale
        strdate = time.strftime("%d-%%s-%Y %H:%M:%S ", ttup[:9])
        odate = strdate % (_MONTH_NAMES[ttup[1]],)
        if ttup[9] is None:
            odate = odate + "+0000"
        else:
            if ttup[9] >= 0:
                sign = "+"
            else:
                sign = "-"
            odate = odate + sign + str(((abs(ttup[9]) // 3600) * 100 + (abs(ttup[9]) % 3600) // 60)).zfill(4)
        _w('INTERNALDATE ' + _quote(odate))

    def spew_rfc822header(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        hdrs = _formatHeaders(msg.getHeaders(True))
        _w('RFC822.HEADER ' + _literal(hdrs))

    def spew_rfc822text(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        _w('RFC822.TEXT ')
        _f()
        return FileProducer(msg.getBodyFile()
            ).beginProducing(self.transport
            )

    def spew_rfc822size(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        _w('RFC822.SIZE ' + str(msg.getSize()))

    def spew_rfc822(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        _w('RFC822 ')
        _f()
        mf = IMessageFile(msg, None)
        if mf is not None:
            return FileProducer(mf.open()
                ).beginProducing(self.transport
                )
        return MessageProducer(msg, None, self._scheduler
            ).beginProducing(self.transport
            )

    def spew_uid(self, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        _w('UID ' + str(msg.getUID()))

    def spew_bodystructure(self, id, msg, _w=None, _f=None):
        _w('BODYSTRUCTURE ' + collapseNestedLists([getBodyStructure(msg, True)]))

    def spew_body(self, part, id, msg, _w=None, _f=None):
        if _w is None:
            _w = self.transport.write
        for p in part.part:
            if msg.isMultipart():
                msg = msg.getSubPart(p)
            elif p > 0:
                # Non-multipart messages have an implicit first part but no
                # other parts - reject any request for any other part.
                raise TypeError("Requested subpart of non-multipart message")

        if part.header:
            hdrs = msg.getHeaders(part.header.negate, *part.header.fields)
            hdrs = _formatHeaders(hdrs)
            _w(str(part) + ' ' + _literal(hdrs))
        elif part.text:
            _w(str(part) + ' ')
            _f()
            return FileProducer(msg.getBodyFile()
                ).beginProducing(self.transport
                )
        elif part.mime:
            hdrs = _formatHeaders(msg.getHeaders(True))
            _w(str(part) + ' ' + _literal(hdrs))
        elif part.empty:
            _w(str(part) + ' ')
            _f()
            if part.part:
                return FileProducer(msg.getBodyFile()
                    ).beginProducing(self.transport
                    )
            else:
                mf = IMessageFile(msg, None)
                if mf is not None:
                    return FileProducer(mf.open()).beginProducing(self.transport)
                return MessageProducer(msg, None, self._scheduler).beginProducing(self.transport)

        else:
            _w('BODY ' + collapseNestedLists([getBodyStructure(msg)]))

    def spewMessage(self, id, msg, query, uid):
        wbuf = WriteBuffer(self.transport)
        write = wbuf.write
        flush = wbuf.flush
        def start():
            write('* %d FETCH (' % (id,))
        def finish():
            write(')\r\n')
        def space():
            write(' ')

        def spew():
            seenUID = False
            start()
            for part in query:
                if part.type == 'uid':
                    seenUID = True
                if part.type == 'body':
                    yield self.spew_body(part, id, msg, write, flush)
                else:
                    f = getattr(self, 'spew_' + part.type)
                    yield f(id, msg, write, flush)
                if part is not query[-1]:
                    space()
            if uid and not seenUID:
                space()
                yield self.spew_uid(id, msg, write, flush)
            finish()
            flush()
        return self._scheduler(spew())

    def __ebFetch(self, failure, tag):
        self.setTimeout(self._oldTimeout)
        del self._oldTimeout
        log.err(failure)
        self.sendBadResponse(tag, 'FETCH failed: ' + str(failure.value))

    def do_STORE(self, tag, messages, mode, flags, uid=0):
        mode = mode.upper()
        silent = mode.endswith('SILENT')
        if mode.startswith('+'):
            mode = 1
        elif mode.startswith('-'):
            mode = -1
        else:
            mode = 0

        maybeDeferred(self.mbox.store, messages, flags, mode, uid=uid).addCallbacks(
            self.__cbStore, self.__ebStore, (tag, self.mbox, uid, silent), None, (tag,), None
        )

    select_STORE = (do_STORE, arg_seqset, arg_atom, arg_flaglist)

    def __cbStore(self, result, tag, mbox, uid, silent):
        if result and not silent:
              for (k, v) in result.iteritems():
                  if uid:
                      uidstr = ' UID %d' % mbox.getUID(k)
                  else:
                      uidstr = ''
                  self.sendUntaggedResponse('%d FETCH (FLAGS (%s)%s)' %
                                            (k, ' '.join(v), uidstr))
        self.sendPositiveResponse(tag, 'STORE completed')

    def __ebStore(self, failure, tag):
        self.sendBadResponse(tag, 'Server error: ' + str(failure.value))

    def do_COPY(self, tag, messages, mailbox, uid=0):
        mailbox = self._parseMbox(mailbox)
        maybeDeferred(self.account.select, mailbox
            ).addCallback(self._cbCopySelectedMailbox, tag, messages, mailbox, uid
            ).addErrback(self._ebCopySelectedMailbox, tag
            )
    select_COPY = (do_COPY, arg_seqset, arg_astring)

    def _cbCopySelectedMailbox(self, mbox, tag, messages, mailbox, uid):
        if not mbox:
            self.sendNegativeResponse(tag, 'No such mailbox: ' + mailbox)
        else:
            maybeDeferred(self.mbox.fetch, messages, uid
                ).addCallback(self.__cbCopy, tag, mbox
                ).addCallback(self.__cbCopied, tag, mbox
                ).addErrback(self.__ebCopy, tag
                )

    def _ebCopySelectedMailbox(self, failure, tag):
        self.sendBadResponse(tag, 'Server error: ' + str(failure.value))

    def __cbCopy(self, messages, tag, mbox):
        # XXX - This should handle failures with a rollback or something
        addedDeferreds = []
        addedIDs = []
        failures = []

        fastCopyMbox = IMessageCopier(mbox, None)
        for (id, msg) in messages:
            if fastCopyMbox is not None:
                d = maybeDeferred(fastCopyMbox.copy, msg)
                addedDeferreds.append(d)
                continue

            # XXX - The following should be an implementation of IMessageCopier.copy
            # on an IMailbox->IMessageCopier adapter.

            flags = msg.getFlags()
            date = msg.getInternalDate()

            body = IMessageFile(msg, None)
            if body is not None:
                bodyFile = body.open()
                d = maybeDeferred(mbox.addMessage, bodyFile, flags, date)
            else:
                def rewind(f):
                    f.seek(0)
                    return f
                buffer = tempfile.TemporaryFile()
                d = MessageProducer(msg, buffer, self._scheduler
                    ).beginProducing(None
                    ).addCallback(lambda _, b=buffer, f=flags, d=date: mbox.addMessage(rewind(b), f, d)
                    )
            addedDeferreds.append(d)
        return defer.DeferredList(addedDeferreds)

    def __cbCopied(self, deferredIds, tag, mbox):
        ids = []
        failures = []
        for (status, result) in deferredIds:
            if status:
                ids.append(result)
            else:
                failures.append(result.value)
        if failures:
            self.sendNegativeResponse(tag, '[ALERT] Some messages were not copied')
        else:
            self.sendPositiveResponse(tag, 'COPY completed')

    def __ebCopy(self, failure, tag):
        self.sendBadResponse(tag, 'COPY failed:' + str(failure.value))
        log.err(failure)

    def do_UID(self, tag, command, line):
        command = command.upper()

        if command not in ('COPY', 'FETCH', 'STORE', 'SEARCH'):
            raise IllegalClientResponse(command)

        self.dispatchCommand(tag, command, line, uid=1)

    select_UID = (do_UID, arg_atom, arg_line)
    #
    # IMailboxListener implementation
    #
    def modeChanged(self, writeable):
        if writeable:
            self.sendUntaggedResponse(message='[READ-WRITE]', async=True)
        else:
            self.sendUntaggedResponse(message='[READ-ONLY]', async=True)

    def flagsChanged(self, newFlags):
        for (mId, flags) in newFlags.iteritems():
            msg = '%d FETCH (FLAGS (%s))' % (mId, ' '.join(flags))
            self.sendUntaggedResponse(msg, async=True)

    def newMessages(self, exists, recent):
        if exists is not None:
            self.sendUntaggedResponse('%d EXISTS' % exists, async=True)
        if recent is not None:
            self.sendUntaggedResponse('%d RECENT' % recent, async=True)


class UnhandledResponse(IMAP4Exception): pass

class NegativeResponse(IMAP4Exception): pass

class NoSupportedAuthentication(IMAP4Exception):
    def __init__(self, serverSupports, clientSupports):
        IMAP4Exception.__init__(self, 'No supported authentication schemes available')
        self.serverSupports = serverSupports
        self.clientSupports = clientSupports

    def __str__(self):
        return (IMAP4Exception.__str__(self)
            + ': Server supports %r, client supports %r'
            % (self.serverSupports, self.clientSupports))

class IllegalServerResponse(IMAP4Exception): pass

TIMEOUT_ERROR = error.TimeoutError()

class IMAP4Client(basic.LineReceiver, policies.TimeoutMixin):
    """IMAP4 client protocol implementation

    @ivar state: A string representing the state the connection is currently
    in.
    """
    implements(IMailboxListener)

    tags = None
    waiting = None
    queued = None
    tagID = 1
    state = None

    startedTLS = False

    # Number of seconds to wait before timing out a connection.
    # If the number is <= 0 no timeout checking will be performed.
    timeout = 0

    # Capabilities are not allowed to change during the session
    # So cache the first response and use that for all later
    # lookups
    _capCache = None

    _memoryFileLimit = 1024 * 1024 * 10

    # Authentication is pluggable.  This maps names to IClientAuthentication
    # objects.
    authenticators = None

    STATUS_CODES = ('OK', 'NO', 'BAD', 'PREAUTH', 'BYE')

    STATUS_TRANSFORMATIONS = {
        'MESSAGES': int, 'RECENT': int, 'UNSEEN': int
    }

    context = None

    def __init__(self, contextFactory = None):
        self.tags = {}
        self.queued = []
        self.authenticators = {}
        self.context = contextFactory

        self._tag = None
        self._parts = None
        self._lastCmd = None

    def registerAuthenticator(self, auth):
        """Register a new form of authentication

        When invoking the authenticate() method of IMAP4Client, the first
        matching authentication scheme found will be used.  The ordering is
        that in which the server lists support authentication schemes.

        @type auth: Implementor of C{IClientAuthentication}
        @param auth: The object to use to perform the client
        side of this authentication scheme.
        """
        self.authenticators[auth.getName().upper()] = auth

    def rawDataReceived(self, data):
        if self.timeout > 0:
            self.resetTimeout()

        self._pendingSize -= len(data)
        if self._pendingSize > 0:
            self._pendingBuffer.write(data)
        else:
            passon = ''
            if self._pendingSize < 0:
                data, passon = data[:self._pendingSize], data[self._pendingSize:]
            self._pendingBuffer.write(data)
            rest = self._pendingBuffer
            self._pendingBuffer = None
            self._pendingSize = None
            rest.seek(0, 0)
            self._parts.append(rest.read())
            self.setLineMode(passon.lstrip('\r\n'))

#    def sendLine(self, line):
#        print 'S:', repr(line)
#        return basic.LineReceiver.sendLine(self, line)

    def _setupForLiteral(self, rest, octets):
        self._pendingBuffer = self.messageFile(octets)
        self._pendingSize = octets
        if self._parts is None:
            self._parts = [rest, '\r\n']
        else:
            self._parts.extend([rest, '\r\n'])
        self.setRawMode()

    def connectionMade(self):
        if self.timeout > 0:
            self.setTimeout(self.timeout)

    def connectionLost(self, reason):
        """We are no longer connected"""
        if self.timeout > 0:
            self.setTimeout(None)
        if self.queued is not None:
            queued = self.queued
            self.queued = None
            for cmd in queued:
                cmd.defer.errback(reason)
        if self.tags is not None:
            tags = self.tags
            self.tags = None
            for cmd in tags.itervalues():
                if cmd is not None and cmd.defer is not None:
                    cmd.defer.errback(reason)


    def lineReceived(self, line):
        """
        Attempt to parse a single line from the server.

        @type line: C{str}
        @param line: The line from the server, without the line delimiter.

        @raise IllegalServerResponse: If the line or some part of the line
            does not represent an allowed message from the server at this time.
        """
#        print 'C: ' + repr(line)
        if self.timeout > 0:
            self.resetTimeout()

        lastPart = line.rfind('{')
        if lastPart != -1:
            lastPart = line[lastPart + 1:]
            if lastPart.endswith('}'):
                # It's a literal a-comin' in
                try:
                    octets = int(lastPart[:-1])
                except ValueError:
                    raise IllegalServerResponse(line)
                if self._parts is None:
                    self._tag, parts = line.split(None, 1)
                else:
                    parts = line
                self._setupForLiteral(parts, octets)
                return

        if self._parts is None:
            # It isn't a literal at all
            self._regularDispatch(line)
        else:
            # If an expression is in progress, no tag is required here
            # Since we didn't find a literal indicator, this expression
            # is done.
            self._parts.append(line)
            tag, rest = self._tag, ''.join(self._parts)
            self._tag = self._parts = None
            self.dispatchCommand(tag, rest)

    def timeoutConnection(self):
        if self._lastCmd and self._lastCmd.defer is not None:
            d, self._lastCmd.defer = self._lastCmd.defer, None
            d.errback(TIMEOUT_ERROR)

        if self.queued:
            for cmd in self.queued:
                if cmd.defer is not None:
                    d, cmd.defer = cmd.defer, d
                    d.errback(TIMEOUT_ERROR)

        self.transport.loseConnection()

    def _regularDispatch(self, line):
        parts = line.split(None, 1)
        if len(parts) != 2:
            parts.append('')
        tag, rest = parts
        self.dispatchCommand(tag, rest)

    def messageFile(self, octets):
        """Create a file to which an incoming message may be written.

        @type octets: C{int}
        @param octets: The number of octets which will be written to the file

        @rtype: Any object which implements C{write(string)} and
        C{seek(int, int)}
        @return: A file-like object
        """
        if octets > self._memoryFileLimit:
            return tempfile.TemporaryFile()
        else:
            return StringIO.StringIO()

    def makeTag(self):
        tag = '%0.4X' % self.tagID
        self.tagID += 1
        return tag

    def dispatchCommand(self, tag, rest):
        if self.state is None:
            f = self.response_UNAUTH
        else:
            f = getattr(self, 'response_' + self.state.upper(), None)
        if f:
            try:
                f(tag, rest)
            except:
                log.err()
                self.transport.loseConnection()
        else:
            log.err("Cannot dispatch: %s, %s, %s" % (self.state, tag, rest))
            self.transport.loseConnection()

    def response_UNAUTH(self, tag, rest):
        if self.state is None:
            # Server greeting, this is
            status, rest = rest.split(None, 1)
            if status.upper() == 'OK':
                self.state = 'unauth'
            elif status.upper() == 'PREAUTH':
                self.state = 'auth'
            else:
                # XXX - This is rude.
                self.transport.loseConnection()
                raise IllegalServerResponse(tag + ' ' + rest)

            b, e = rest.find('['), rest.find(']')
            if b != -1 and e != -1:
                self.serverGreeting(
                    self.__cbCapabilities(
                        ([parseNestedParens(rest[b + 1:e])], None)))
            else:
                self.serverGreeting(None)
        else:
            self._defaultHandler(tag, rest)

    def response_AUTH(self, tag, rest):
        self._defaultHandler(tag, rest)

    def _defaultHandler(self, tag, rest):
        if tag == '*' or tag == '+':
            if not self.waiting:
                self._extraInfo([parseNestedParens(rest)])
            else:
                cmd = self.tags[self.waiting]
                if tag == '+':
                    cmd.continuation(rest)
                else:
                    cmd.lines.append(rest)
        else:
            try:
                cmd = self.tags[tag]
            except KeyError:
                # XXX - This is rude.
                self.transport.loseConnection()
                raise IllegalServerResponse(tag + ' ' + rest)
            else:
                status, line = rest.split(None, 1)
                if status == 'OK':
                    # Give them this last line, too
                    cmd.finish(rest, self._extraInfo)
                else:
                    cmd.defer.errback(IMAP4Exception(line))
                del self.tags[tag]
                self.waiting = None
                self._flushQueue()

    def _flushQueue(self):
        if self.queued:
            cmd = self.queued.pop(0)
            t = self.makeTag()
            self.tags[t] = cmd
            self.sendLine(cmd.format(t))
            self.waiting = t

    def _extraInfo(self, lines):
        # XXX - This is terrible.
        # XXX - Also, this should collapse temporally proximate calls into single
        #       invocations of IMailboxListener methods, where possible.
        flags = {}
        recent = exists = None
        for response in lines:
            elements = len(response)
            if elements == 1 and response[0] == ['READ-ONLY']:
                self.modeChanged(False)
            elif elements == 1 and response[0] == ['READ-WRITE']:
                self.modeChanged(True)
            elif elements == 2 and response[1] == 'EXISTS':
                exists = int(response[0])
            elif elements == 2 and response[1] == 'RECENT':
                recent = int(response[0])
            elif elements == 3 and response[1] == 'FETCH':
                mId = int(response[0])
                values = self._parseFetchPairs(response[2])
                flags.setdefault(mId, []).extend(values.get('FLAGS', ()))
            else:
                log.msg('Unhandled unsolicited response: %s' % (response,))

        if flags:
            self.flagsChanged(flags)
        if recent is not None or exists is not None:
            self.newMessages(exists, recent)

    def sendCommand(self, cmd):
        cmd.defer = defer.Deferred()
        if self.waiting:
            self.queued.append(cmd)
            return cmd.defer
        t = self.makeTag()
        self.tags[t] = cmd
        self.sendLine(cmd.format(t))
        self.waiting = t
        self._lastCmd = cmd
        return cmd.defer

    def getCapabilities(self, useCache=1):
        """Request the capabilities available on this server.

        This command is allowed in any state of connection.

        @type useCache: C{bool}
        @param useCache: Specify whether to use the capability-cache or to
        re-retrieve the capabilities from the server.  Server capabilities
        should never change, so for normal use, this flag should never be
        false.

        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with a
        dictionary mapping capability types to lists of supported
        mechanisms, or to None if a support list is not applicable.
        """
        if useCache and self._capCache is not None:
            return defer.succeed(self._capCache)
        cmd = 'CAPABILITY'
        resp = ('CAPABILITY',)
        d = self.sendCommand(Command(cmd, wantResponse=resp))
        d.addCallback(self.__cbCapabilities)
        return d

    def __cbCapabilities(self, (lines, tagline)):
        caps = {}
        for rest in lines:
            for cap in rest[1:]:
                parts = cap.split('=', 1)
                if len(parts) == 1:
                    category, value = parts[0], None
                else:
                    category, value = parts
                caps.setdefault(category, []).append(value)

        # Preserve a non-ideal API for backwards compatibility.  It would
        # probably be entirely sensible to have an object with a wider API than
        # dict here so this could be presented less insanely.
        for category in caps:
            if caps[category] == [None]:
                caps[category] = None
        self._capCache = caps
        return caps

    def logout(self):
        """Inform the server that we are done with the connection.

        This command is allowed in any state of connection.

        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with None
        when the proper server acknowledgement has been received.
        """
        d = self.sendCommand(Command('LOGOUT', wantResponse=('BYE',)))
        d.addCallback(self.__cbLogout)
        return d

    def __cbLogout(self, (lines, tagline)):
        self.transport.loseConnection()
        # We don't particularly care what the server said
        return None


    def noop(self):
        """Perform no operation.

        This command is allowed in any state of connection.

        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with a list
        of untagged status updates the server responds with.
        """
        d = self.sendCommand(Command('NOOP'))
        d.addCallback(self.__cbNoop)
        return d

    def __cbNoop(self, (lines, tagline)):
        # Conceivable, this is elidable.
        # It is, afterall, a no-op.
        return lines

    def startTLS(self, contextFactory=None):
        """
        Initiates a 'STARTTLS' request and negotiates the TLS / SSL
        Handshake.

        @param contextFactory: The TLS / SSL Context Factory to
        leverage.  If the contextFactory is None the IMAP4Client will
        either use the current TLS / SSL Context Factory or attempt to
        create a new one.

        @type contextFactory: C{ssl.ClientContextFactory}

        @return: A Deferred which fires when the transport has been
        secured according to the given contextFactory, or which fails
        if the transport cannot be secured.
        """
        assert not self.startedTLS, "Client and Server are currently communicating via TLS"

        if contextFactory is None:
            contextFactory = self._getContextFactory()

        if contextFactory is None:
            return defer.fail(IMAP4Exception(
                "IMAP4Client requires a TLS context to "
                "initiate the STARTTLS handshake"))

        if 'STARTTLS' not in self._capCache:
            return defer.fail(IMAP4Exception(
                "Server does not support secure communication "
                "via TLS / SSL"))

        tls = interfaces.ITLSTransport(self.transport, None)
        if tls is None:
            return defer.fail(IMAP4Exception(
                "IMAP4Client transport does not implement "
                "interfaces.ITLSTransport"))

        d = self.sendCommand(Command('STARTTLS'))
        d.addCallback(self._startedTLS, contextFactory)
        d.addCallback(lambda _: self.getCapabilities())
        return d


    def authenticate(self, secret):
        """Attempt to enter the authenticated state with the server

        This command is allowed in the Non-Authenticated state.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the authentication
        succeeds and whose errback will be invoked otherwise.
        """
        if self._capCache is None:
            d = self.getCapabilities()
        else:
            d = defer.succeed(self._capCache)
        d.addCallback(self.__cbAuthenticate, secret)
        return d

    def __cbAuthenticate(self, caps, secret):
        auths = caps.get('AUTH', ())
        for scheme in auths:
            if scheme.upper() in self.authenticators:
                cmd = Command('AUTHENTICATE', scheme, (),
                              self.__cbContinueAuth, scheme,
                              secret)
                return self.sendCommand(cmd)

        if self.startedTLS:
            return defer.fail(NoSupportedAuthentication(
                auths, self.authenticators.keys()))
        else:
            def ebStartTLS(err):
                err.trap(IMAP4Exception)
                # We couldn't negotiate TLS for some reason
                return defer.fail(NoSupportedAuthentication(
                    auths, self.authenticators.keys()))

            d = self.startTLS()
            d.addErrback(ebStartTLS)
            d.addCallback(lambda _: self.getCapabilities())
            d.addCallback(self.__cbAuthTLS, secret)
            return d


    def __cbContinueAuth(self, rest, scheme, secret):
        try:
            chal = base64.decodestring(rest + '\n')
        except binascii.Error:
            self.sendLine('*')
            raise IllegalServerResponse(rest)
        else:
            auth = self.authenticators[scheme]
            chal = auth.challengeResponse(secret, chal)
            self.sendLine(base64.encodestring(chal).strip())

    def __cbAuthTLS(self, caps, secret):
        auths = caps.get('AUTH', ())
        for scheme in auths:
            if scheme.upper() in self.authenticators:
                cmd = Command('AUTHENTICATE', scheme, (),
                              self.__cbContinueAuth, scheme,
                              secret)
                return self.sendCommand(cmd)
        raise NoSupportedAuthentication(auths, self.authenticators.keys())


    def login(self, username, password):
        """Authenticate with the server using a username and password

        This command is allowed in the Non-Authenticated state.  If the
        server supports the STARTTLS capability and our transport supports
        TLS, TLS is negotiated before the login command is issued.

        A more secure way to log in is to use C{startTLS} or
        C{authenticate} or both.

        @type username: C{str}
        @param username: The username to log in with

        @type password: C{str}
        @param password: The password to log in with

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if login is successful
        and whose errback is invoked otherwise.
        """
        d = maybeDeferred(self.getCapabilities)
        d.addCallback(self.__cbLoginCaps, username, password)
        return d

    def serverGreeting(self, caps):
        """Called when the server has sent us a greeting.

        @type caps: C{dict}
        @param caps: Capabilities the server advertised in its greeting.
        """

    def _getContextFactory(self):
        if self.context is not None:
            return self.context
        try:
            from twisted.internet import ssl
        except ImportError:
            return None
        else:
            context = ssl.ClientContextFactory()
            context.method = ssl.SSL.TLSv1_METHOD
            return context

    def __cbLoginCaps(self, capabilities, username, password):
        # If the server advertises STARTTLS, we might want to try to switch to TLS
        tryTLS = 'STARTTLS' in capabilities

        # If our transport supports switching to TLS, we might want to try to switch to TLS.
        tlsableTransport = interfaces.ITLSTransport(self.transport, None) is not None

        # If our transport is not already using TLS, we might want to try to switch to TLS.
        nontlsTransport = interfaces.ISSLTransport(self.transport, None) is None

        if not self.startedTLS and tryTLS and tlsableTransport and nontlsTransport:
            d = self.startTLS()

            d.addCallbacks(
                self.__cbLoginTLS,
                self.__ebLoginTLS,
                callbackArgs=(username, password),
                )
            return d
        else:
            if nontlsTransport:
                log.msg("Server has no TLS support. logging in over cleartext!")
            args = ' '.join((_quote(username), _quote(password)))
            return self.sendCommand(Command('LOGIN', args))

    def _startedTLS(self, result, context):
        self.transport.startTLS(context)
        self._capCache = None
        self.startedTLS = True
        return result

    def __cbLoginTLS(self, result, username, password):
        args = ' '.join((_quote(username), _quote(password)))
        return self.sendCommand(Command('LOGIN', args))

    def __ebLoginTLS(self, failure):
        log.err(failure)
        return failure

    def namespace(self):
        """Retrieve information about the namespaces available to this account

        This command is allowed in the Authenticated and Selected states.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with namespace
        information.  An example of this information is::

            [[['', '/']], [], []]

        which indicates a single personal namespace called '' with '/'
        as its hierarchical delimiter, and no shared or user namespaces.
        """
        cmd = 'NAMESPACE'
        resp = ('NAMESPACE',)
        d = self.sendCommand(Command(cmd, wantResponse=resp))
        d.addCallback(self.__cbNamespace)
        return d

    def __cbNamespace(self, (lines, last)):
        for parts in lines:
            if len(parts) == 4 and parts[0] == 'NAMESPACE':
                return [e or [] for e in parts[1:]]
        log.err("No NAMESPACE response to NAMESPACE command")
        return [[], [], []]


    def select(self, mailbox):
        """
        Select a mailbox

        This command is allowed in the Authenticated and Selected states.

        @type mailbox: C{str}
        @param mailbox: The name of the mailbox to select

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with mailbox
        information if the select is successful and whose errback is
        invoked otherwise.  Mailbox information consists of a dictionary
        with the following keys and values::

                FLAGS: A list of strings containing the flags settable on
                        messages in this mailbox.

                EXISTS: An integer indicating the number of messages in this
                        mailbox.

                RECENT: An integer indicating the number of "recent"
                        messages in this mailbox.

                UNSEEN: The message sequence number (an integer) of the
                        first unseen message in the mailbox.

                PERMANENTFLAGS: A list of strings containing the flags that
                        can be permanently set on messages in this mailbox.

                UIDVALIDITY: An integer uniquely identifying this mailbox.
        """
        cmd = 'SELECT'
        args = _prepareMailboxName(mailbox)
        resp = ('FLAGS', 'EXISTS', 'RECENT', 'UNSEEN', 'PERMANENTFLAGS', 'UIDVALIDITY')
        d = self.sendCommand(Command(cmd, args, wantResponse=resp))
        d.addCallback(self.__cbSelect, 1)
        return d


    def examine(self, mailbox):
        """Select a mailbox in read-only mode

        This command is allowed in the Authenticated and Selected states.

        @type mailbox: C{str}
        @param mailbox: The name of the mailbox to examine

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with mailbox
        information if the examine is successful and whose errback
        is invoked otherwise.  Mailbox information consists of a dictionary
        with the following keys and values::

            'FLAGS': A list of strings containing the flags settable on
                        messages in this mailbox.

            'EXISTS': An integer indicating the number of messages in this
                        mailbox.

            'RECENT': An integer indicating the number of \"recent\"
                        messages in this mailbox.

            'UNSEEN': An integer indicating the number of messages not
                        flagged \\Seen in this mailbox.

            'PERMANENTFLAGS': A list of strings containing the flags that
                        can be permanently set on messages in this mailbox.

            'UIDVALIDITY': An integer uniquely identifying this mailbox.
        """
        cmd = 'EXAMINE'
        args = _prepareMailboxName(mailbox)
        resp = ('FLAGS', 'EXISTS', 'RECENT', 'UNSEEN', 'PERMANENTFLAGS', 'UIDVALIDITY')
        d = self.sendCommand(Command(cmd, args, wantResponse=resp))
        d.addCallback(self.__cbSelect, 0)
        return d


    def _intOrRaise(self, value, phrase):
        """
        Parse C{value} as an integer and return the result or raise
        L{IllegalServerResponse} with C{phrase} as an argument if C{value}
        cannot be parsed as an integer.
        """
        try:
            return int(value)
        except ValueError:
            raise IllegalServerResponse(phrase)


    def __cbSelect(self, (lines, tagline), rw):
        """
        Handle lines received in response to a SELECT or EXAMINE command.

        See RFC 3501, section 6.3.1.
        """
        # In the absense of specification, we are free to assume:
        #   READ-WRITE access
        datum = {'READ-WRITE': rw}
        lines.append(parseNestedParens(tagline))
        for split in lines:
            if len(split) > 0 and split[0].upper() == 'OK':
                # Handle all the kinds of OK response.
                content = split[1]
                key = content[0].upper()
                if key == 'READ-ONLY':
                    datum['READ-WRITE'] = False
                elif key == 'READ-WRITE':
                    datum['READ-WRITE'] = True
                elif key == 'UIDVALIDITY':
                    datum['UIDVALIDITY'] = self._intOrRaise(
                        content[1], split)
                elif key == 'UNSEEN':
                    datum['UNSEEN'] = self._intOrRaise(content[1], split)
                elif key == 'UIDNEXT':
                    datum['UIDNEXT'] = self._intOrRaise(content[1], split)
                elif key == 'PERMANENTFLAGS':
                    datum['PERMANENTFLAGS'] = tuple(content[1])
                else:
                    log.err('Unhandled SELECT response (2): %s' % (split,))
            elif len(split) == 2:
                # Handle FLAGS, EXISTS, and RECENT
                if split[0].upper() == 'FLAGS':
                    datum['FLAGS'] = tuple(split[1])
                elif isinstance(split[1], str):
                    # Must make sure things are strings before treating them as
                    # strings since some other forms of response have nesting in
                    # places which results in lists instead.
                    if split[1].upper() == 'EXISTS':
                        datum['EXISTS'] = self._intOrRaise(split[0], split)
                    elif split[1].upper() == 'RECENT':
                        datum['RECENT'] = self._intOrRaise(split[0], split)
                    else:
                        log.err('Unhandled SELECT response (0): %s' % (split,))
                else:
                    log.err('Unhandled SELECT response (1): %s' % (split,))
            else:
                log.err('Unhandled SELECT response (4): %s' % (split,))
        return datum


    def create(self, name):
        """Create a new mailbox on the server

        This command is allowed in the Authenticated and Selected states.

        @type name: C{str}
        @param name: The name of the mailbox to create.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the mailbox creation
        is successful and whose errback is invoked otherwise.
        """
        return self.sendCommand(Command('CREATE', _prepareMailboxName(name)))

    def delete(self, name):
        """Delete a mailbox

        This command is allowed in the Authenticated and Selected states.

        @type name: C{str}
        @param name: The name of the mailbox to delete.

        @rtype: C{Deferred}
        @return: A deferred whose calblack is invoked if the mailbox is
        deleted successfully and whose errback is invoked otherwise.
        """
        return self.sendCommand(Command('DELETE', _prepareMailboxName(name)))

    def rename(self, oldname, newname):
        """Rename a mailbox

        This command is allowed in the Authenticated and Selected states.

        @type oldname: C{str}
        @param oldname: The current name of the mailbox to rename.

        @type newname: C{str}
        @param newname: The new name to give the mailbox.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the rename is
        successful and whose errback is invoked otherwise.
        """
        oldname = _prepareMailboxName(oldname)
        newname = _prepareMailboxName(newname)
        return self.sendCommand(Command('RENAME', ' '.join((oldname, newname))))

    def subscribe(self, name):
        """Add a mailbox to the subscription list

        This command is allowed in the Authenticated and Selected states.

        @type name: C{str}
        @param name: The mailbox to mark as 'active' or 'subscribed'

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the subscription
        is successful and whose errback is invoked otherwise.
        """
        return self.sendCommand(Command('SUBSCRIBE', _prepareMailboxName(name)))

    def unsubscribe(self, name):
        """Remove a mailbox from the subscription list

        This command is allowed in the Authenticated and Selected states.

        @type name: C{str}
        @param name: The mailbox to unsubscribe

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the unsubscription
        is successful and whose errback is invoked otherwise.
        """
        return self.sendCommand(Command('UNSUBSCRIBE', _prepareMailboxName(name)))

    def list(self, reference, wildcard):
        """List a subset of the available mailboxes

        This command is allowed in the Authenticated and Selected states.

        @type reference: C{str}
        @param reference: The context in which to interpret C{wildcard}

        @type wildcard: C{str}
        @param wildcard: The pattern of mailbox names to match, optionally
        including either or both of the '*' and '%' wildcards.  '*' will
        match zero or more characters and cross hierarchical boundaries.
        '%' will also match zero or more characters, but is limited to a
        single hierarchical level.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a list of C{tuple}s,
        the first element of which is a C{tuple} of mailbox flags, the second
        element of which is the hierarchy delimiter for this mailbox, and the
        third of which is the mailbox name; if the command is unsuccessful,
        the deferred's errback is invoked instead.
        """
        cmd = 'LIST'
        args = '"%s" "%s"' % (reference, wildcard.encode('imap4-utf-7'))
        resp = ('LIST',)
        d = self.sendCommand(Command(cmd, args, wantResponse=resp))
        d.addCallback(self.__cbList, 'LIST')
        return d

    def lsub(self, reference, wildcard):
        """List a subset of the subscribed available mailboxes

        This command is allowed in the Authenticated and Selected states.

        The parameters and returned object are the same as for the C{list}
        method, with one slight difference: Only mailboxes which have been
        subscribed can be included in the resulting list.
        """
        cmd = 'LSUB'
        args = '"%s" "%s"' % (reference, wildcard.encode('imap4-utf-7'))
        resp = ('LSUB',)
        d = self.sendCommand(Command(cmd, args, wantResponse=resp))
        d.addCallback(self.__cbList, 'LSUB')
        return d

    def __cbList(self, (lines, last), command):
        results = []
        for parts in lines:
            if len(parts) == 4 and parts[0] == command:
                parts[1] = tuple(parts[1])
                results.append(tuple(parts[1:]))
        return results

    def status(self, mailbox, *names):
        """
        Retrieve the status of the given mailbox

        This command is allowed in the Authenticated and Selected states.

        @type mailbox: C{str}
        @param mailbox: The name of the mailbox to query

        @type *names: C{str}
        @param *names: The status names to query.  These may be any number of:
            C{'MESSAGES'}, C{'RECENT'}, C{'UIDNEXT'}, C{'UIDVALIDITY'}, and
            C{'UNSEEN'}.

        @rtype: C{Deferred}
        @return: A deferred which fires with with the status information if the
            command is successful and whose errback is invoked otherwise.  The
            status information is in the form of a C{dict}.  Each element of
            C{names} is a key in the dictionary.  The value for each key is the
            corresponding response from the server.
        """
        cmd = 'STATUS'
        args = "%s (%s)" % (_prepareMailboxName(mailbox), ' '.join(names))
        resp = ('STATUS',)
        d = self.sendCommand(Command(cmd, args, wantResponse=resp))
        d.addCallback(self.__cbStatus)
        return d

    def __cbStatus(self, (lines, last)):
        status = {}
        for parts in lines:
            if parts[0] == 'STATUS':
                items = parts[2]
                items = [items[i:i+2] for i in range(0, len(items), 2)]
                status.update(dict(items))
        for k in status.keys():
            t = self.STATUS_TRANSFORMATIONS.get(k)
            if t:
                try:
                    status[k] = t(status[k])
                except Exception, e:
                    raise IllegalServerResponse('(%s %s): %s' % (k, status[k], str(e)))
        return status

    def append(self, mailbox, message, flags = (), date = None):
        """Add the given message to the given mailbox.

        This command is allowed in the Authenticated and Selected states.

        @type mailbox: C{str}
        @param mailbox: The mailbox to which to add this message.

        @type message: Any file-like object
        @param message: The message to add, in RFC822 format.  Newlines
        in this file should be \\r\\n-style.

        @type flags: Any iterable of C{str}
        @param flags: The flags to associated with this message.

        @type date: C{str}
        @param date: The date to associate with this message.  This should
        be of the format DD-MM-YYYY HH:MM:SS +/-HHMM.  For example, in
        Eastern Standard Time, on July 1st 2004 at half past 1 PM,
        \"01-07-2004 13:30:00 -0500\".

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when this command
        succeeds or whose errback is invoked if it fails.
        """
        message.seek(0, 2)
        L = message.tell()
        message.seek(0, 0)
        fmt = '%s (%s)%s {%d}'
        if date:
            date = ' "%s"' % date
        else:
            date = ''
        cmd = fmt % (
            _prepareMailboxName(mailbox), ' '.join(flags),
            date, L
        )
        d = self.sendCommand(Command('APPEND', cmd, (), self.__cbContinueAppend, message))
        return d

    def __cbContinueAppend(self, lines, message):
        s = basic.FileSender()
        return s.beginFileTransfer(message, self.transport, None
            ).addCallback(self.__cbFinishAppend)

    def __cbFinishAppend(self, foo):
        self.sendLine('')

    def check(self):
        """Tell the server to perform a checkpoint

        This command is allowed in the Selected state.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when this command
        succeeds or whose errback is invoked if it fails.
        """
        return self.sendCommand(Command('CHECK'))

    def close(self):
        """Return the connection to the Authenticated state.

        This command is allowed in the Selected state.

        Issuing this command will also remove all messages flagged \\Deleted
        from the selected mailbox if it is opened in read-write mode,
        otherwise it indicates success by no messages are removed.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when the command
        completes successfully or whose errback is invoked if it fails.
        """
        return self.sendCommand(Command('CLOSE'))


    def expunge(self):
        """Return the connection to the Authenticate state.

        This command is allowed in the Selected state.

        Issuing this command will perform the same actions as issuing the
        close command, but will also generate an 'expunge' response for
        every message deleted.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a list of the
        'expunge' responses when this command is successful or whose errback
        is invoked otherwise.
        """
        cmd = 'EXPUNGE'
        resp = ('EXPUNGE',)
        d = self.sendCommand(Command(cmd, wantResponse=resp))
        d.addCallback(self.__cbExpunge)
        return d


    def __cbExpunge(self, (lines, last)):
        ids = []
        for parts in lines:
            if len(parts) == 2 and parts[1] == 'EXPUNGE':
                ids.append(self._intOrRaise(parts[0], parts))
        return ids


    def search(self, *queries, **kwarg):
        """Search messages in the currently selected mailbox

        This command is allowed in the Selected state.

        Any non-zero number of queries are accepted by this method, as
        returned by the C{Query}, C{Or}, and C{Not} functions.

        One keyword argument is accepted: if uid is passed in with a non-zero
        value, the server is asked to return message UIDs instead of message
        sequence numbers.

        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with a list of all
        the message sequence numbers return by the search, or whose errback
        will be invoked if there is an error.
        """
        if kwarg.get('uid'):
            cmd = 'UID SEARCH'
        else:
            cmd = 'SEARCH'
        args = ' '.join(queries)
        d = self.sendCommand(Command(cmd, args, wantResponse=(cmd,)))
        d.addCallback(self.__cbSearch)
        return d


    def __cbSearch(self, (lines, end)):
        ids = []
        for parts in lines:
            if len(parts) > 0 and parts[0] == 'SEARCH':
                ids.extend([self._intOrRaise(p, parts) for p in parts[1:]])
        return ids


    def fetchUID(self, messages, uid=0):
        """Retrieve the unique identifier for one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message sequence numbers to unique message identifiers, or whose
        errback is invoked if there is an error.
        """
        return self._fetch(messages, useUID=uid, uid=1)


    def fetchFlags(self, messages, uid=0):
        """Retrieve the flags for one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: The messages for which to retrieve flags.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to lists of flags, or whose errback is invoked if
        there is an error.
        """
        return self._fetch(str(messages), useUID=uid, flags=1)


    def fetchInternalDate(self, messages, uid=0):
        """Retrieve the internal date associated with one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: The messages for which to retrieve the internal date.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to date strings, or whose errback is invoked
        if there is an error.  Date strings take the format of
        \"day-month-year time timezone\".
        """
        return self._fetch(str(messages), useUID=uid, internaldate=1)


    def fetchEnvelope(self, messages, uid=0):
        """Retrieve the envelope data for one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: The messages for which to retrieve envelope data.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to envelope data, or whose errback is invoked
        if there is an error.  Envelope data consists of a sequence of the
        date, subject, from, sender, reply-to, to, cc, bcc, in-reply-to,
        and message-id header fields.  The date, subject, in-reply-to, and
        message-id fields are strings, while the from, sender, reply-to,
        to, cc, and bcc fields contain address data.  Address data consists
        of a sequence of name, source route, mailbox name, and hostname.
        Fields which are not present for a particular address may be C{None}.
        """
        return self._fetch(str(messages), useUID=uid, envelope=1)


    def fetchBodyStructure(self, messages, uid=0):
        """Retrieve the structure of the body of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: The messages for which to retrieve body structure
        data.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to body structure data, or whose errback is invoked
        if there is an error.  Body structure data describes the MIME-IMB
        format of a message and consists of a sequence of mime type, mime
        subtype, parameters, content id, description, encoding, and size.
        The fields following the size field are variable: if the mime
        type/subtype is message/rfc822, the contained message's envelope
        information, body structure data, and number of lines of text; if
        the mime type is text, the number of lines of text.  Extension fields
        may also be included; if present, they are: the MD5 hash of the body,
        body disposition, body language.
        """
        return self._fetch(messages, useUID=uid, bodystructure=1)


    def fetchSimplifiedBody(self, messages, uid=0):
        """Retrieve the simplified body structure of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to body data, or whose errback is invoked
        if there is an error.  The simplified body structure is the same
        as the body structure, except that extension fields will never be
        present.
        """
        return self._fetch(messages, useUID=uid, body=1)


    def fetchMessage(self, messages, uid=0):
        """Retrieve one or more entire messages

        This command is allowed in the Selected state.

        @type messages: L{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: L{Deferred}

        @return: A L{Deferred} which will fire with a C{dict} mapping message
            sequence numbers to C{dict}s giving message data for the
            corresponding message.  If C{uid} is true, the inner dictionaries
            have a C{'UID'} key mapped to a C{str} giving the UID for the
            message.  The text of the message is a C{str} associated with the
            C{'RFC822'} key in each dictionary.
        """
        return self._fetch(messages, useUID=uid, rfc822=1)


    def fetchHeaders(self, messages, uid=0):
        """Retrieve headers of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dicts of message headers, or whose errback is
        invoked if there is an error.
        """
        return self._fetch(messages, useUID=uid, rfc822header=1)


    def fetchBody(self, messages, uid=0):
        """Retrieve body text of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to file-like objects containing body text, or whose
        errback is invoked if there is an error.
        """
        return self._fetch(messages, useUID=uid, rfc822text=1)


    def fetchSize(self, messages, uid=0):
        """Retrieve the size, in octets, of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to sizes, or whose errback is invoked if there is
        an error.
        """
        return self._fetch(messages, useUID=uid, rfc822size=1)


    def fetchFull(self, messages, uid=0):
        """Retrieve several different fields of one or more messages

        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate},
        C{fetchSize}, C{fetchEnvelope}, and C{fetchSimplifiedBody}
        functions.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dict of the retrieved data values, or whose
        errback is invoked if there is an error.  They dictionary keys
        are "flags", "date", "size", "envelope", and "body".
        """
        return self._fetch(
            messages, useUID=uid, flags=1, internaldate=1,
            rfc822size=1, envelope=1, body=1)


    def fetchAll(self, messages, uid=0):
        """Retrieve several different fields of one or more messages

        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate},
        C{fetchSize}, and C{fetchEnvelope} functions.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dict of the retrieved data values, or whose
        errback is invoked if there is an error.  They dictionary keys
        are "flags", "date", "size", and "envelope".
        """
        return self._fetch(
            messages, useUID=uid, flags=1, internaldate=1,
            rfc822size=1, envelope=1)


    def fetchFast(self, messages, uid=0):
        """Retrieve several different fields of one or more messages

        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate}, and
        C{fetchSize} functions.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dict of the retrieved data values, or whose
        errback is invoked if there is an error.  They dictionary keys are
        "flags", "date", and "size".
        """
        return self._fetch(
            messages, useUID=uid, flags=1, internaldate=1, rfc822size=1)


    def _parseFetchPairs(self, fetchResponseList):
        """
        Given the result of parsing a single I{FETCH} response, construct a
        C{dict} mapping response keys to response values.

        @param fetchResponseList: The result of parsing a I{FETCH} response
            with L{parseNestedParens} and extracting just the response data
            (that is, just the part that comes after C{"FETCH"}).  The form
            of this input (and therefore the output of this method) is very
            disagreable.  A valuable improvement would be to enumerate the
            possible keys (representing them as structured objects of some
            sort) rather than using strings and tuples of tuples of strings
            and so forth.  This would allow the keys to be documented more
            easily and would allow for a much simpler application-facing API
            (one not based on looking up somewhat hard to predict keys in a
            dict).  Since C{fetchResponseList} notionally represents a
            flattened sequence of pairs (identifying keys followed by their
            associated values), collapsing such complex elements of this
            list as C{["BODY", ["HEADER.FIELDS", ["SUBJECT"]]]} into a
            single object would also greatly simplify the implementation of
            this method.

        @return: A C{dict} of the response data represented by C{pairs}.  Keys
            in this dictionary are things like C{"RFC822.TEXT"}, C{"FLAGS"}, or
            C{("BODY", ("HEADER.FIELDS", ("SUBJECT",)))}.  Values are entirely
            dependent on the key with which they are associated, but retain the
            same structured as produced by L{parseNestedParens}.
        """
        values = {}
        responseParts = iter(fetchResponseList)
        while True:
            try:
                key = responseParts.next()
            except StopIteration:
                break

            try:
                value = responseParts.next()
            except StopIteration:
                raise IllegalServerResponse(
                    "Not enough arguments", fetchResponseList)

            # The parsed forms of responses like:
            #
            # BODY[] VALUE
            # BODY[TEXT] VALUE
            # BODY[HEADER.FIELDS (SUBJECT)] VALUE
            # BODY[HEADER.FIELDS (SUBJECT)]<N.M> VALUE
            #
            # are:
            #
            # ["BODY", [], VALUE]
            # ["BODY", ["TEXT"], VALUE]
            # ["BODY", ["HEADER.FIELDS", ["SUBJECT"]], VALUE]
            # ["BODY", ["HEADER.FIELDS", ["SUBJECT"]], "<N.M>", VALUE]
            #
            # Here, check for these cases and grab as many extra elements as
            # necessary to retrieve the body information.
            if key in ("BODY", "BODY.PEEK") and isinstance(value, list) and len(value) < 3:
                if len(value) < 2:
                    key = (key, tuple(value))
                else:
                    key = (key, (value[0], tuple(value[1])))
                try:
                    value = responseParts.next()
                except StopIteration:
                    raise IllegalServerResponse(
                        "Not enough arguments", fetchResponseList)

                # Handle partial ranges
                if value.startswith('<') and value.endswith('>'):
                    try:
                        int(value[1:-1])
                    except ValueError:
                        # This isn't really a range, it's some content.
                        pass
                    else:
                        key = key + (value,)
                        try:
                            value = responseParts.next()
                        except StopIteration:
                            raise IllegalServerResponse(
                                "Not enough arguments", fetchResponseList)

            values[key] = value
        return values


    def _cbFetch(self, (lines, last), requestedParts, structured):
        info = {}
        for parts in lines:
            if len(parts) == 3 and parts[1] == 'FETCH':
                id = self._intOrRaise(parts[0], parts)
                if id not in info:
                    info[id] = [parts[2]]
                else:
                    info[id][0].extend(parts[2])

        results = {}
        for (messageId, values) in info.iteritems():
            mapping = self._parseFetchPairs(values[0])
            results.setdefault(messageId, {}).update(mapping)

        flagChanges = {}
        for messageId in results.keys():
            values = results[messageId]
            for part in values.keys():
                if part not in requestedParts and part == 'FLAGS':
                    flagChanges[messageId] = values['FLAGS']
                    # Find flags in the result and get rid of them.
                    for i in range(len(info[messageId][0])):
                        if info[messageId][0][i] == 'FLAGS':
                            del info[messageId][0][i:i+2]
                            break
                    del values['FLAGS']
                    if not values:
                        del results[messageId]

        if flagChanges:
            self.flagsChanged(flagChanges)

        if structured:
            return results
        else:
            return info


    def fetchSpecific(self, messages, uid=0, headerType=None,
                      headerNumber=None, headerArgs=None, peek=None,
                      offset=None, length=None):
        """Retrieve a specific section of one or more messages

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @type headerType: C{str}
        @param headerType: If specified, must be one of HEADER,
        HEADER.FIELDS, HEADER.FIELDS.NOT, MIME, or TEXT, and will determine
        which part of the message is retrieved.  For HEADER.FIELDS and
        HEADER.FIELDS.NOT, C{headerArgs} must be a sequence of header names.
        For MIME, C{headerNumber} must be specified.

        @type headerNumber: C{int} or C{int} sequence
        @param headerNumber: The nested rfc822 index specifying the
        entity to retrieve.  For example, C{1} retrieves the first
        entity of the message, and C{(2, 1, 3}) retrieves the 3rd
        entity inside the first entity inside the second entity of
        the message.

        @type headerArgs: A sequence of C{str}
        @param headerArgs: If C{headerType} is HEADER.FIELDS, these are the
        headers to retrieve.  If it is HEADER.FIELDS.NOT, these are the
        headers to exclude from retrieval.

        @type peek: C{bool}
        @param peek: If true, cause the server to not set the \\Seen
        flag on this message as a result of this command.

        @type offset: C{int}
        @param offset: The number of octets at the beginning of the result
        to skip.

        @type length: C{int}
        @param length: The number of octets to retrieve.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a mapping of
        message numbers to retrieved data, or whose errback is invoked
        if there is an error.
        """
        fmt = '%s BODY%s[%s%s%s]%s'
        if headerNumber is None:
            number = ''
        elif isinstance(headerNumber, int):
            number = str(headerNumber)
        else:
            number = '.'.join(map(str, headerNumber))
        if headerType is None:
            header = ''
        elif number:
            header = '.' + headerType
        else:
            header = headerType
        if header and headerType not in ('TEXT', 'MIME'):
            if headerArgs is not None:
                payload = ' (%s)' % ' '.join(headerArgs)
            else:
                payload = ' ()'
        else:
            payload = ''
        if offset is None:
            extra = ''
        else:
            extra = '<%d.%d>' % (offset, length)
        fetch = uid and 'UID FETCH' or 'FETCH'
        cmd = fmt % (messages, peek and '.PEEK' or '', number, header, payload, extra)
        d = self.sendCommand(Command(fetch, cmd, wantResponse=('FETCH',)))
        d.addCallback(self._cbFetch, (), False)
        return d


    def _fetch(self, messages, useUID=0, **terms):
        fetch = useUID and 'UID FETCH' or 'FETCH'

        if 'rfc822text' in terms:
            del terms['rfc822text']
            terms['rfc822.text'] = True
        if 'rfc822size' in terms:
            del terms['rfc822size']
            terms['rfc822.size'] = True
        if 'rfc822header' in terms:
            del terms['rfc822header']
            terms['rfc822.header'] = True

        cmd = '%s (%s)' % (messages, ' '.join([s.upper() for s in terms.keys()]))
        d = self.sendCommand(Command(fetch, cmd, wantResponse=('FETCH',)))
        d.addCallback(self._cbFetch, map(str.upper, terms.keys()), True)
        return d

    def setFlags(self, messages, flags, silent=1, uid=0):
        """Set the flags for one or more messages.

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type flags: Any iterable of C{str}
        @param flags: The flags to set

        @type silent: C{bool}
        @param silent: If true, cause the server to supress its verbose
        response.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a list of the
        the server's responses (C{[]} if C{silent} is true) or whose
        errback is invoked if there is an error.
        """
        return self._store(str(messages), 'FLAGS', silent, flags, uid)

    def addFlags(self, messages, flags, silent=1, uid=0):
        """Add to the set flags for one or more messages.

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type flags: Any iterable of C{str}
        @param flags: The flags to set

        @type silent: C{bool}
        @param silent: If true, cause the server to supress its verbose
        response.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a list of the
        the server's responses (C{[]} if C{silent} is true) or whose
        errback is invoked if there is an error.
        """
        return self._store(str(messages),'+FLAGS', silent, flags, uid)

    def removeFlags(self, messages, flags, silent=1, uid=0):
        """Remove from the set flags for one or more messages.

        This command is allowed in the Selected state.

        @type messages: C{MessageSet} or C{str}
        @param messages: A message sequence set

        @type flags: Any iterable of C{str}
        @param flags: The flags to set

        @type silent: C{bool}
        @param silent: If true, cause the server to supress its verbose
        response.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a list of the
        the server's responses (C{[]} if C{silent} is true) or whose
        errback is invoked if there is an error.
        """
        return self._store(str(messages), '-FLAGS', silent, flags, uid)


    def _store(self, messages, cmd, silent, flags, uid):
        if silent:
            cmd = cmd + '.SILENT'
        store = uid and 'UID STORE' or 'STORE'
        args = ' '.join((messages, cmd, '(%s)' % ' '.join(flags)))
        d = self.sendCommand(Command(store, args, wantResponse=('FETCH',)))
        expected = ()
        if not silent:
            expected = ('FLAGS',)
        d.addCallback(self._cbFetch, expected, True)
        return d


    def copy(self, messages, mailbox, uid):
        """Copy the specified messages to the specified mailbox.

        This command is allowed in the Selected state.

        @type messages: C{str}
        @param messages: A message sequence set

        @type mailbox: C{str}
        @param mailbox: The mailbox to which to copy the messages

        @type uid: C{bool}
        @param uid: If true, the C{messages} refers to message UIDs, rather
        than message sequence numbers.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a true value
        when the copy is successful, or whose errback is invoked if there
        is an error.
        """
        if uid:
            cmd = 'UID COPY'
        else:
            cmd = 'COPY'
        args = '%s %s' % (messages, _prepareMailboxName(mailbox))
        return self.sendCommand(Command(cmd, args))

    #
    # IMailboxListener methods
    #
    def modeChanged(self, writeable):
        """Override me"""

    def flagsChanged(self, newFlags):
        """Override me"""

    def newMessages(self, exists, recent):
        """Override me"""


class IllegalIdentifierError(IMAP4Exception): pass

def parseIdList(s, lastMessageId=None):
    """
    Parse a message set search key into a C{MessageSet}.

    @type s: C{str}
    @param s: A string description of a id list, for example "1:3, 4:*"

    @type lastMessageId: C{int}
    @param lastMessageId: The last message sequence id or UID, depending on
        whether we are parsing the list in UID or sequence id context. The
        caller should pass in the correct value.

    @rtype: C{MessageSet}
    @return: A C{MessageSet} that contains the ids defined in the list
    """
    res = MessageSet()
    parts = s.split(',')
    for p in parts:
        if ':' in p:
            low, high = p.split(':', 1)
            try:
                if low == '*':
                    low = None
                else:
                    low = long(low)
                if high == '*':
                    high = None
                else:
                    high = long(high)
                if low is high is None:
                    # *:* does not make sense
                    raise IllegalIdentifierError(p)
                # non-positive values are illegal according to RFC 3501
                if ((low is not None and low <= 0) or
                    (high is not None and high <= 0)):
                    raise IllegalIdentifierError(p)
                # star means "highest value of an id in the mailbox"
                high = high or lastMessageId
                low = low or lastMessageId

                # RFC says that 2:4 and 4:2 are equivalent
                if low > high:
                    low, high = high, low
                res.extend((low, high))
            except ValueError:
                raise IllegalIdentifierError(p)
        else:
            try:
                if p == '*':
                    p = None
                else:
                    p = long(p)
                if p is not None and p <= 0:
                    raise IllegalIdentifierError(p)
            except ValueError:
                raise IllegalIdentifierError(p)
            else:
                res.extend(p or lastMessageId)
    return res

class IllegalQueryError(IMAP4Exception): pass

_SIMPLE_BOOL = (
    'ALL', 'ANSWERED', 'DELETED', 'DRAFT', 'FLAGGED', 'NEW', 'OLD', 'RECENT',
    'SEEN', 'UNANSWERED', 'UNDELETED', 'UNDRAFT', 'UNFLAGGED', 'UNSEEN'
)

_NO_QUOTES = (
    'LARGER', 'SMALLER', 'UID'
)

def Query(sorted=0, **kwarg):
    """Create a query string

    Among the accepted keywords are::

        all         : If set to a true value, search all messages in the
                      current mailbox

        answered    : If set to a true value, search messages flagged with
                      \\Answered

        bcc         : A substring to search the BCC header field for

        before      : Search messages with an internal date before this
                      value.  The given date should be a string in the format
                      of 'DD-Mon-YYYY'.  For example, '03-Mar-2003'.

        body        : A substring to search the body of the messages for

        cc          : A substring to search the CC header field for

        deleted     : If set to a true value, search messages flagged with
                      \\Deleted

        draft       : If set to a true value, search messages flagged with
                      \\Draft

        flagged     : If set to a true value, search messages flagged with
                      \\Flagged

        from        : A substring to search the From header field for

        header      : A two-tuple of a header name and substring to search
                      for in that header

        keyword     : Search for messages with the given keyword set

        larger      : Search for messages larger than this number of octets

        messages    : Search only the given message sequence set.

        new         : If set to a true value, search messages flagged with
                      \\Recent but not \\Seen

        old         : If set to a true value, search messages not flagged with
                      \\Recent

        on          : Search messages with an internal date which is on this
                      date.  The given date should be a string in the format
                      of 'DD-Mon-YYYY'.  For example, '03-Mar-2003'.

        recent      : If set to a true value, search for messages flagged with
                      \\Recent

        seen        : If set to a true value, search for messages flagged with
                      \\Seen

        sentbefore  : Search for messages with an RFC822 'Date' header before
                      this date.  The given date should be a string in the format
                      of 'DD-Mon-YYYY'.  For example, '03-Mar-2003'.

        senton      : Search for messages with an RFC822 'Date' header which is
                      on this date  The given date should be a string in the format
                      of 'DD-Mon-YYYY'.  For example, '03-Mar-2003'.

        sentsince   : Search for messages with an RFC822 'Date' header which is
                      after this date.  The given date should be a string in the format
                      of 'DD-Mon-YYYY'.  For example, '03-Mar-2003'.

        since       : Search for messages with an internal date that is after
                      this date..  The given date should be a string in the format
                      of 'DD-Mon-YYYY'.  For example, '03-Mar-2003'.

        smaller     : Search for messages smaller than this number of octets

        subject     : A substring to search the 'subject' header for

        text        : A substring to search the entire message for

        to          : A substring to search the 'to' header for

        uid         : Search only the messages in the given message set

        unanswered  : If set to a true value, search for messages not
                      flagged with \\Answered

        undeleted   : If set to a true value, search for messages not
                      flagged with \\Deleted

        undraft     : If set to a true value, search for messages not
                      flagged with \\Draft

        unflagged   : If set to a true value, search for messages not
                      flagged with \\Flagged

        unkeyword   : Search for messages without the given keyword set

        unseen      : If set to a true value, search for messages not
                      flagged with \\Seen

    @type sorted: C{bool}
    @param sorted: If true, the output will be sorted, alphabetically.
    The standard does not require it, but it makes testing this function
    easier.  The default is zero, and this should be acceptable for any
    application.

    @rtype: C{str}
    @return: The formatted query string
    """
    cmd = []
    keys = kwarg.keys()
    if sorted:
        keys.sort()
    for k in keys:
        v = kwarg[k]
        k = k.upper()
        if k in _SIMPLE_BOOL and v:
           cmd.append(k)
        elif k == 'HEADER':
            cmd.extend([k, v[0], '"%s"' % (v[1],)])
        elif k not in _NO_QUOTES:
           cmd.extend([k, '"%s"' % (v,)])
        else:
           cmd.extend([k, '%s' % (v,)])
    if len(cmd) > 1:
        return '(%s)' % ' '.join(cmd)
    else:
        return ' '.join(cmd)

def Or(*args):
    """The disjunction of two or more queries"""
    if len(args) < 2:
        raise IllegalQueryError, args
    elif len(args) == 2:
        return '(OR %s %s)' % args
    else:
        return '(OR %s %s)' % (args[0], Or(*args[1:]))

def Not(query):
    """The negation of a query"""
    return '(NOT %s)' % (query,)

class MismatchedNesting(IMAP4Exception):
    pass

class MismatchedQuoting(IMAP4Exception):
    pass

def wildcardToRegexp(wildcard, delim=None):
    wildcard = wildcard.replace('*', '(?:.*?)')
    if delim is None:
        wildcard = wildcard.replace('%', '(?:.*?)')
    else:
        wildcard = wildcard.replace('%', '(?:(?:[^%s])*?)' % re.escape(delim))
    return re.compile(wildcard, re.I)

def splitQuoted(s):
    """Split a string into whitespace delimited tokens

    Tokens that would otherwise be separated but are surrounded by \"
    remain as a single token.  Any token that is not quoted and is
    equal to \"NIL\" is tokenized as C{None}.

    @type s: C{str}
    @param s: The string to be split

    @rtype: C{list} of C{str}
    @return: A list of the resulting tokens

    @raise MismatchedQuoting: Raised if an odd number of quotes are present
    """
    s = s.strip()
    result = []
    word = []
    inQuote = inWord = False
    for i, c in enumerate(s):
        if c == '"':
            if i and s[i-1] == '\\':
                word.pop()
                word.append('"')
            elif not inQuote:
                inQuote = True
            else:
                inQuote = False
                result.append(''.join(word))
                word = []
        elif not inWord and not inQuote and c not in ('"' + string.whitespace):
            inWord = True
            word.append(c)
        elif inWord and not inQuote and c in string.whitespace:
            w = ''.join(word)
            if w == 'NIL':
                result.append(None)
            else:
                result.append(w)
            word = []
            inWord = False
        elif inWord or inQuote:
            word.append(c)

    if inQuote:
        raise MismatchedQuoting(s)
    if inWord:
        w = ''.join(word)
        if w == 'NIL':
            result.append(None)
        else:
            result.append(w)

    return result



def splitOn(sequence, predicate, transformers):
    result = []
    mode = predicate(sequence[0])
    tmp = [sequence[0]]
    for e in sequence[1:]:
        p = predicate(e)
        if p != mode:
            result.extend(transformers[mode](tmp))
            tmp = [e]
            mode = p
        else:
            tmp.append(e)
    result.extend(transformers[mode](tmp))
    return result

def collapseStrings(results):
    """
    Turns a list of length-one strings and lists into a list of longer
    strings and lists.  For example,

    ['a', 'b', ['c', 'd']] is returned as ['ab', ['cd']]

    @type results: C{list} of C{str} and C{list}
    @param results: The list to be collapsed

    @rtype: C{list} of C{str} and C{list}
    @return: A new list which is the collapsed form of C{results}
    """
    copy = []
    begun = None
    listsList = [isinstance(s, types.ListType) for s in results]

    pred = lambda e: isinstance(e, types.TupleType)
    tran = {
        0: lambda e: splitQuoted(''.join(e)),
        1: lambda e: [''.join([i[0] for i in e])]
    }
    for (i, c, isList) in zip(range(len(results)), results, listsList):
        if isList:
            if begun is not None:
                copy.extend(splitOn(results[begun:i], pred, tran))
                begun = None
            copy.append(collapseStrings(c))
        elif begun is None:
            begun = i
    if begun is not None:
        copy.extend(splitOn(results[begun:], pred, tran))
    return copy


def parseNestedParens(s, handleLiteral = 1):
    """Parse an s-exp-like string into a more useful data structure.

    @type s: C{str}
    @param s: The s-exp-like string to parse

    @rtype: C{list} of C{str} and C{list}
    @return: A list containing the tokens present in the input.

    @raise MismatchedNesting: Raised if the number or placement
    of opening or closing parenthesis is invalid.
    """
    s = s.strip()
    inQuote = 0
    contentStack = [[]]
    try:
        i = 0
        L = len(s)
        while i < L:
            c = s[i]
            if inQuote:
                if c == '\\':
                    contentStack[-1].append(s[i:i+2])
                    i += 2
                    continue
                elif c == '"':
                    inQuote = not inQuote
                contentStack[-1].append(c)
                i += 1
            else:
                if c == '"':
                    contentStack[-1].append(c)
                    inQuote = not inQuote
                    i += 1
                elif handleLiteral and c == '{':
                    end = s.find('}', i)
                    if end == -1:
                        raise ValueError, "Malformed literal"
                    literalSize = int(s[i+1:end])
                    contentStack[-1].append((s[end+3:end+3+literalSize],))
                    i = end + 3 + literalSize
                elif c == '(' or c == '[':
                    contentStack.append([])
                    i += 1
                elif c == ')' or c == ']':
                    contentStack[-2].append(contentStack.pop())
                    i += 1
                else:
                    contentStack[-1].append(c)
                    i += 1
    except IndexError:
        raise MismatchedNesting(s)
    if len(contentStack) != 1:
        raise MismatchedNesting(s)
    return collapseStrings(contentStack[0])

def _quote(s):
    return '"%s"' % (s.replace('\\', '\\\\').replace('"', '\\"'),)

def _literal(s):
    return '{%d}\r\n%s' % (len(s), s)

class DontQuoteMe:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

_ATOM_SPECIALS = '(){ %*"'
def _needsQuote(s):
    if s == '':
        return 1
    for c in s:
        if c < '\x20' or c > '\x7f':
            return 1
        if c in _ATOM_SPECIALS:
            return 1
    return 0

def _prepareMailboxName(name):
    name = name.encode('imap4-utf-7')
    if _needsQuote(name):
        return _quote(name)
    return name

def _needsLiteral(s):
    # Change this to "return 1" to wig out stupid clients
    return '\n' in s or '\r' in s or len(s) > 1000

def collapseNestedLists(items):
    """Turn a nested list structure into an s-exp-like string.

    Strings in C{items} will be sent as literals if they contain CR or LF,
    otherwise they will be quoted.  References to None in C{items} will be
    translated to the atom NIL.  Objects with a 'read' attribute will have
    it called on them with no arguments and the returned string will be
    inserted into the output as a literal.  Integers will be converted to
    strings and inserted into the output unquoted.  Instances of
    C{DontQuoteMe} will be converted to strings and inserted into the output
    unquoted.

    This function used to be much nicer, and only quote things that really
    needed to be quoted (and C{DontQuoteMe} did not exist), however, many
    broken IMAP4 clients were unable to deal with this level of sophistication,
    forcing the current behavior to be adopted for practical reasons.

    @type items: Any iterable

    @rtype: C{str}
    """
    pieces = []
    for i in items:
        if i is None:
            pieces.extend([' ', 'NIL'])
        elif isinstance(i, (DontQuoteMe, int, long)):
            pieces.extend([' ', str(i)])
        elif isinstance(i, types.StringTypes):
            if _needsLiteral(i):
                pieces.extend([' ', '{', str(len(i)), '}', IMAP4Server.delimiter, i])
            else:
                pieces.extend([' ', _quote(i)])
        elif hasattr(i, 'read'):
            d = i.read()
            pieces.extend([' ', '{', str(len(d)), '}', IMAP4Server.delimiter, d])
        else:
            pieces.extend([' ', '(%s)' % (collapseNestedLists(i),)])
    return ''.join(pieces[1:])


class IClientAuthentication(Interface):
    def getName():
        """Return an identifier associated with this authentication scheme.

        @rtype: C{str}
        """

    def challengeResponse(secret, challenge):
        """Generate a challenge response string"""



class CramMD5ClientAuthenticator:
    implements(IClientAuthentication)

    def __init__(self, user):
        self.user = user

    def getName(self):
        return "CRAM-MD5"

    def challengeResponse(self, secret, chal):
        response = hmac.HMAC(secret, chal).hexdigest()
        return '%s %s' % (self.user, response)



class LOGINAuthenticator:
    implements(IClientAuthentication)

    def __init__(self, user):
        self.user = user
        self.challengeResponse = self.challengeUsername

    def getName(self):
        return "LOGIN"

    def challengeUsername(self, secret, chal):
        # Respond to something like "Username:"
        self.challengeResponse = self.challengeSecret
        return self.user

    def challengeSecret(self, secret, chal):
        # Respond to something like "Password:"
        return secret

class PLAINAuthenticator:
    implements(IClientAuthentication)

    def __init__(self, user):
        self.user = user

    def getName(self):
        return "PLAIN"

    def challengeResponse(self, secret, chal):
        return '\0%s\0%s' % (self.user, secret)


class MailboxException(IMAP4Exception): pass

class MailboxCollision(MailboxException):
    def __str__(self):
        return 'Mailbox named %s already exists' % self.args

class NoSuchMailbox(MailboxException):
    def __str__(self):
        return 'No mailbox named %s exists' % self.args

class ReadOnlyMailbox(MailboxException):
    def __str__(self):
        return 'Mailbox open in read-only state'


class IAccount(Interface):
    """Interface for Account classes

    Implementors of this interface should consider implementing
    C{INamespacePresenter}.
    """

    def addMailbox(name, mbox = None):
        """Add a new mailbox to this account

        @type name: C{str}
        @param name: The name associated with this mailbox.  It may not
        contain multiple hierarchical parts.

        @type mbox: An object implementing C{IMailbox}
        @param mbox: The mailbox to associate with this name.  If C{None},
        a suitable default is created and used.

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the creation succeeds, or a deferred whose
        callback will be invoked when the creation succeeds.

        @raise MailboxException: Raised if this mailbox cannot be added for
        some reason.  This may also be raised asynchronously, if a C{Deferred}
        is returned.
        """

    def create(pathspec):
        """Create a new mailbox from the given hierarchical name.

        @type pathspec: C{str}
        @param pathspec: The full hierarchical name of a new mailbox to create.
        If any of the inferior hierarchical names to this one do not exist,
        they are created as well.

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the creation succeeds, or a deferred whose
        callback will be invoked when the creation succeeds.

        @raise MailboxException: Raised if this mailbox cannot be added.
        This may also be raised asynchronously, if a C{Deferred} is
        returned.
        """

    def select(name, rw=True):
        """Acquire a mailbox, given its name.

        @type name: C{str}
        @param name: The mailbox to acquire

        @type rw: C{bool}
        @param rw: If a true value, request a read-write version of this
        mailbox.  If a false value, request a read-only version.

        @rtype: Any object implementing C{IMailbox} or C{Deferred}
        @return: The mailbox object, or a C{Deferred} whose callback will
        be invoked with the mailbox object.  None may be returned if the
        specified mailbox may not be selected for any reason.
        """

    def delete(name):
        """Delete the mailbox with the specified name.

        @type name: C{str}
        @param name: The mailbox to delete.

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is successfully deleted, or a
        C{Deferred} whose callback will be invoked when the deletion
        completes.

        @raise MailboxException: Raised if this mailbox cannot be deleted.
        This may also be raised asynchronously, if a C{Deferred} is returned.
        """

    def rename(oldname, newname):
        """Rename a mailbox

        @type oldname: C{str}
        @param oldname: The current name of the mailbox to rename.

        @type newname: C{str}
        @param newname: The new name to associate with the mailbox.

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is successfully renamed, or a
        C{Deferred} whose callback will be invoked when the rename operation
        is completed.

        @raise MailboxException: Raised if this mailbox cannot be
        renamed.  This may also be raised asynchronously, if a C{Deferred}
        is returned.
        """

    def isSubscribed(name):
        """Check the subscription status of a mailbox

        @type name: C{str}
        @param name: The name of the mailbox to check

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the given mailbox is currently subscribed
        to, a false value otherwise.  A C{Deferred} may also be returned
        whose callback will be invoked with one of these values.
        """

    def subscribe(name):
        """Subscribe to a mailbox

        @type name: C{str}
        @param name: The name of the mailbox to subscribe to

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is subscribed to successfully,
        or a Deferred whose callback will be invoked with this value when
        the subscription is successful.

        @raise MailboxException: Raised if this mailbox cannot be
        subscribed to.  This may also be raised asynchronously, if a
        C{Deferred} is returned.
        """

    def unsubscribe(name):
        """Unsubscribe from a mailbox

        @type name: C{str}
        @param name: The name of the mailbox to unsubscribe from

        @rtype: C{Deferred} or C{bool}
        @return: A true value if the mailbox is unsubscribed from successfully,
        or a Deferred whose callback will be invoked with this value when
        the unsubscription is successful.

        @raise MailboxException: Raised if this mailbox cannot be
        unsubscribed from.  This may also be raised asynchronously, if a
        C{Deferred} is returned.
        """

    def listMailboxes(ref, wildcard):
        """List all the mailboxes that meet a certain criteria

        @type ref: C{str}
        @param ref: The context in which to apply the wildcard

        @type wildcard: C{str}
        @param wildcard: An expression against which to match mailbox names.
        '*' matches any number of characters in a mailbox name, and '%'
        matches similarly, but will not match across hierarchical boundaries.

        @rtype: C{list} of C{tuple}
        @return: A list of C{(mailboxName, mailboxObject)} which meet the
        given criteria.  C{mailboxObject} should implement either
        C{IMailboxInfo} or C{IMailbox}.  A Deferred may also be returned.
        """

class INamespacePresenter(Interface):
    def getPersonalNamespaces():
        """Report the available personal namespaces.

        Typically there should be only one personal namespace.  A common
        name for it is \"\", and its hierarchical delimiter is usually
        \"/\".

        @rtype: iterable of two-tuples of strings
        @return: The personal namespaces and their hierarchical delimiters.
        If no namespaces of this type exist, None should be returned.
        """

    def getSharedNamespaces():
        """Report the available shared namespaces.

        Shared namespaces do not belong to any individual user but are
        usually to one or more of them.  Examples of shared namespaces
        might be \"#news\" for a usenet gateway.

        @rtype: iterable of two-tuples of strings
        @return: The shared namespaces and their hierarchical delimiters.
        If no namespaces of this type exist, None should be returned.
        """

    def getUserNamespaces():
        """Report the available user namespaces.

        These are namespaces that contain folders belonging to other users
        access to which this account has been granted.

        @rtype: iterable of two-tuples of strings
        @return: The user namespaces and their hierarchical delimiters.
        If no namespaces of this type exist, None should be returned.
        """


class MemoryAccount(object):
    implements(IAccount, INamespacePresenter)

    mailboxes = None
    subscriptions = None
    top_id = 0

    def __init__(self, name):
        self.name = name
        self.mailboxes = {}
        self.subscriptions = []

    def allocateID(self):
        id = self.top_id
        self.top_id += 1
        return id

    ##
    ## IAccount
    ##
    def addMailbox(self, name, mbox = None):
        name = name.upper()
        if name in self.mailboxes:
            raise MailboxCollision, name
        if mbox is None:
            mbox = self._emptyMailbox(name, self.allocateID())
        self.mailboxes[name] = mbox
        return 1

    def create(self, pathspec):
        paths = filter(None, pathspec.split('/'))
        for accum in range(1, len(paths)):
            try:
                self.addMailbox('/'.join(paths[:accum]))
            except MailboxCollision:
                pass
        try:
            self.addMailbox('/'.join(paths))
        except MailboxCollision:
            if not pathspec.endswith('/'):
                return False
        return True

    def _emptyMailbox(self, name, id):
        raise NotImplementedError

    def select(self, name, readwrite=1):
        return self.mailboxes.get(name.upper())

    def delete(self, name):
        name = name.upper()
        # See if this mailbox exists at all
        mbox = self.mailboxes.get(name)
        if not mbox:
            raise MailboxException("No such mailbox")
        # See if this box is flagged \Noselect
        if r'\Noselect' in mbox.getFlags():
            # Check for hierarchically inferior mailboxes with this one
            # as part of their root.
            for others in self.mailboxes.keys():
                if others != name and others.startswith(name):
                    raise MailboxException, "Hierarchically inferior mailboxes exist and \\Noselect is set"
        mbox.destroy()

        # iff there are no hierarchically inferior names, we will
        # delete it from our ken.
        if self._inferiorNames(name) > 1:
            del self.mailboxes[name]

    def rename(self, oldname, newname):
        oldname = oldname.upper()
        newname = newname.upper()
        if oldname not in self.mailboxes:
            raise NoSuchMailbox, oldname

        inferiors = self._inferiorNames(oldname)
        inferiors = [(o, o.replace(oldname, newname, 1)) for o in inferiors]

        for (old, new) in inferiors:
            if new in self.mailboxes:
                raise MailboxCollision, new

        for (old, new) in inferiors:
            self.mailboxes[new] = self.mailboxes[old]
            del self.mailboxes[old]

    def _inferiorNames(self, name):
        inferiors = []
        for infname in self.mailboxes.keys():
            if infname.startswith(name):
                inferiors.append(infname)
        return inferiors

    def isSubscribed(self, name):
        return name.upper() in self.subscriptions

    def subscribe(self, name):
        name = name.upper()
        if name not in self.subscriptions:
            self.subscriptions.append(name)

    def unsubscribe(self, name):
        name = name.upper()
        if name not in self.subscriptions:
            raise MailboxException, "Not currently subscribed to " + name
        self.subscriptions.remove(name)

    def listMailboxes(self, ref, wildcard):
        ref = self._inferiorNames(ref.upper())
        wildcard = wildcardToRegexp(wildcard, '/')
        return [(i, self.mailboxes[i]) for i in ref if wildcard.match(i)]

    ##
    ## INamespacePresenter
    ##
    def getPersonalNamespaces(self):
        return [["", "/"]]

    def getSharedNamespaces(self):
        return None

    def getOtherNamespaces(self):
        return None



_statusRequestDict = {
    'MESSAGES': 'getMessageCount',
    'RECENT': 'getRecentCount',
    'UIDNEXT': 'getUIDNext',
    'UIDVALIDITY': 'getUIDValidity',
    'UNSEEN': 'getUnseenCount'
}
def statusRequestHelper(mbox, names):
    r = {}
    for n in names:
        r[n] = getattr(mbox, _statusRequestDict[n.upper()])()
    return r

def parseAddr(addr):
    if addr is None:
        return [(None, None, None),]
    addrs = email.Utils.getaddresses([addr])
    return [[fn or None, None] + addr.split('@') for fn, addr in addrs]

def getEnvelope(msg):
    headers = msg.getHeaders(True)
    date = headers.get('date')
    subject = headers.get('subject')
    from_ = headers.get('from')
    sender = headers.get('sender', from_)
    reply_to = headers.get('reply-to', from_)
    to = headers.get('to')
    cc = headers.get('cc')
    bcc = headers.get('bcc')
    in_reply_to = headers.get('in-reply-to')
    mid = headers.get('message-id')
    return (date, subject, parseAddr(from_), parseAddr(sender),
        reply_to and parseAddr(reply_to), to and parseAddr(to),
        cc and parseAddr(cc), bcc and parseAddr(bcc), in_reply_to, mid)

def getLineCount(msg):
    # XXX - Super expensive, CACHE THIS VALUE FOR LATER RE-USE
    # XXX - This must be the number of lines in the ENCODED version
    lines = 0
    for _ in msg.getBodyFile():
        lines += 1
    return lines

def unquote(s):
    if s[0] == s[-1] == '"':
        return s[1:-1]
    return s


def _getContentType(msg):
    """
    Return a two-tuple of the main and subtype of the given message.
    """
    attrs = None
    mm = msg.getHeaders(False, 'content-type').get('content-type', None)
    if mm:
        mm = ''.join(mm.splitlines())
        mimetype = mm.split(';')
        if mimetype:
            type = mimetype[0].split('/', 1)
            if len(type) == 1:
                major = type[0]
                minor = None
            elif len(type) == 2:
                major, minor = type
            else:
                major = minor = None
            attrs = dict(x.strip().lower().split('=', 1) for x in mimetype[1:])
        else:
            major = minor = None
    else:
        major = minor = None
    return major, minor, attrs



def _getMessageStructure(message):
    """
    Construct an appropriate type of message structure object for the given
    message object.

    @param message: A L{IMessagePart} provider

    @return: A L{_MessageStructure} instance of the most specific type available
        for the given message, determined by inspecting the MIME type of the
        message.
    """
    main, subtype, attrs = _getContentType(message)
    if main is not None:
        main = main.lower()
    if subtype is not None:
        subtype = subtype.lower()
    if main == 'multipart':
        return _MultipartMessageStructure(message, subtype, attrs)
    elif (main, subtype) == ('message', 'rfc822'):
        return _RFC822MessageStructure(message, main, subtype, attrs)
    elif main == 'text':
        return _TextMessageStructure(message, main, subtype, attrs)
    else:
        return _SinglepartMessageStructure(message, main, subtype, attrs)



class _MessageStructure(object):
    """
    L{_MessageStructure} is a helper base class for message structure classes
    representing the structure of particular kinds of messages, as defined by
    their MIME type.
    """
    def __init__(self, message, attrs):
        """
        @param message: An L{IMessagePart} provider which this structure object
            reports on.

        @param attrs: A C{dict} giving the parameters of the I{Content-Type}
            header of the message.
        """
        self.message = message
        self.attrs = attrs


    def _disposition(self, disp):
        """
        Parse a I{Content-Disposition} header into a two-sequence of the
        disposition and a flattened list of its parameters.

        @return: C{None} if there is no disposition header value, a C{list} with
            two elements otherwise.
        """
        if disp:
            disp = disp.split('; ')
            if len(disp) == 1:
                disp = (disp[0].lower(), None)
            elif len(disp) > 1:
                # XXX Poorly tested parser
                params = [x for param in disp[1:] for x in param.split('=', 1)]
                disp = [disp[0].lower(), params]
            return disp
        else:
            return None


    def _unquotedAttrs(self):
        """
        @return: The I{Content-Type} parameters, unquoted, as a flat list with
            each Nth element giving a parameter name and N+1th element giving
            the corresponding parameter value.
        """
        if self.attrs:
            unquoted = [(k, unquote(v)) for (k, v) in self.attrs.iteritems()]
            return [y for x in sorted(unquoted) for y in x]
        return None



class _SinglepartMessageStructure(_MessageStructure):
    """
    L{_SinglepartMessageStructure} represents the message structure of a
    non-I{multipart/*} message.
    """
    _HEADERS = [
        'content-id', 'content-description',
        'content-transfer-encoding']

    def __init__(self, message, main, subtype, attrs):
        """
        @param message: An L{IMessagePart} provider which this structure object
            reports on.

        @param main: A C{str} giving the main MIME type of the message (for
            example, C{"text"}).

        @param subtype: A C{str} giving the MIME subtype of the message (for
            example, C{"plain"}).

        @param attrs: A C{dict} giving the parameters of the I{Content-Type}
            header of the message.
        """
        _MessageStructure.__init__(self, message, attrs)
        self.main = main
        self.subtype = subtype
        self.attrs = attrs


    def _basicFields(self):
        """
        Return a list of the basic fields for a single-part message.
        """
        headers = self.message.getHeaders(False, *self._HEADERS)

        # Number of octets total
        size = self.message.getSize()

        major, minor = self.main, self.subtype

        # content-type parameter list
        unquotedAttrs = self._unquotedAttrs()

        return [
            major, minor, unquotedAttrs,
            headers.get('content-id'),
            headers.get('content-description'),
            headers.get('content-transfer-encoding'),
            size,
            ]


    def encode(self, extended):
        """
        Construct and return a list of the basic and extended fields for a
        single-part message.  The list suitable to be encoded into a BODY or
        BODYSTRUCTURE response.
        """
        result = self._basicFields()
        if extended:
            result.extend(self._extended())
        return result


    def _extended(self):
        """
        The extension data of a non-multipart body part are in the
        following order:

          1. body MD5

             A string giving the body MD5 value as defined in [MD5].

          2. body disposition

             A parenthesized list with the same content and function as
             the body disposition for a multipart body part.

          3. body language

             A string or parenthesized list giving the body language
             value as defined in [LANGUAGE-TAGS].

          4. body location

             A string list giving the body content URI as defined in
             [LOCATION].

        """
        result = []
        headers = self.message.getHeaders(
            False, 'content-md5', 'content-disposition',
            'content-language', 'content-language')

        result.append(headers.get('content-md5'))
        result.append(self._disposition(headers.get('content-disposition')))
        result.append(headers.get('content-language'))
        result.append(headers.get('content-location'))

        return result



class _TextMessageStructure(_SinglepartMessageStructure):
    """
    L{_TextMessageStructure} represents the message structure of a I{text/*}
    message.
    """
    def encode(self, extended):
        """
        A body type of type TEXT contains, immediately after the basic
        fields, the size of the body in text lines.  Note that this
        size is the size in its content transfer encoding and not the
        resulting size after any decoding.
        """
        result = _SinglepartMessageStructure._basicFields(self)
        result.append(getLineCount(self.message))
        if extended:
            result.extend(self._extended())
        return result



class _RFC822MessageStructure(_SinglepartMessageStructure):
    """
    L{_RFC822MessageStructure} represents the message structure of a
    I{message/rfc822} message.
    """
    def encode(self, extended):
        """
        A body type of type MESSAGE and subtype RFC822 contains,
        immediately after the basic fields, the envelope structure,
        body structure, and size in text lines of the encapsulated
        message.
        """
        result = _SinglepartMessageStructure.encode(self, extended)
        contained = self.message.getSubPart(0)
        result.append(getEnvelope(contained))
        result.append(getBodyStructure(contained, False))
        result.append(getLineCount(contained))
        return result



class _MultipartMessageStructure(_MessageStructure):
    """
    L{_MultipartMessageStructure} represents the message structure of a
    I{multipart/*} message.
    """
    def __init__(self, message, subtype, attrs):
        """
        @param message: An L{IMessagePart} provider which this structure object
            reports on.

        @param subtype: A C{str} giving the MIME subtype of the message (for
            example, C{"plain"}).

        @param attrs: A C{dict} giving the parameters of the I{Content-Type}
            header of the message.
        """
        _MessageStructure.__init__(self, message, attrs)
        self.subtype = subtype


    def _getParts(self):
        """
        Return an iterator over all of the sub-messages of this message.
        """
        i = 0
        while True:
            try:
                part = self.message.getSubPart(i)
            except IndexError:
                break
            else:
                yield part
                i += 1


    def encode(self, extended):
        """
        Encode each sub-message and added the additional I{multipart} fields.
        """
        result = [_getMessageStructure(p).encode(extended) for p in self._getParts()]
        result.append(self.subtype)
        if extended:
            result.extend(self._extended())
        return result


    def _extended(self):
        """
        The extension data of a multipart body part are in the following order:

          1. body parameter parenthesized list
               A parenthesized list of attribute/value pairs [e.g., ("foo"
               "bar" "baz" "rag") where "bar" is the value of "foo", and
               "rag" is the value of "baz"] as defined in [MIME-IMB].

          2. body disposition
               A parenthesized list, consisting of a disposition type
               string, followed by a parenthesized list of disposition
               attribute/value pairs as defined in [DISPOSITION].

          3. body language
               A string or parenthesized list giving the body language
               value as defined in [LANGUAGE-TAGS].

          4. body location
               A string list giving the body content URI as defined in
               [LOCATION].
        """
        result = []
        headers = self.message.getHeaders(
            False, 'content-language', 'content-location',
            'content-disposition')

        result.append(self._unquotedAttrs())
        result.append(self._disposition(headers.get('content-disposition')))
        result.append(headers.get('content-language', None))
        result.append(headers.get('content-location', None))

        return result



def getBodyStructure(msg, extended=False):
    """
    RFC 3501, 7.4.2, BODYSTRUCTURE::

      A parenthesized list that describes the [MIME-IMB] body structure of a
      message.  This is computed by the server by parsing the [MIME-IMB] header
      fields, defaulting various fields as necessary.

        For example, a simple text message of 48 lines and 2279 octets can have
        a body structure of: ("TEXT" "PLAIN" ("CHARSET" "US-ASCII") NIL NIL
        "7BIT" 2279 48)

    This is represented as::

        ["TEXT", "PLAIN", ["CHARSET", "US-ASCII"], None, None, "7BIT", 2279, 48]

    These basic fields are documented in the RFC as:

      1. body type

         A string giving the content media type name as defined in
         [MIME-IMB].

      2. body subtype

         A string giving the content subtype name as defined in
         [MIME-IMB].

      3. body parameter parenthesized list

         A parenthesized list of attribute/value pairs [e.g., ("foo"
         "bar" "baz" "rag") where "bar" is the value of "foo" and
         "rag" is the value of "baz"] as defined in [MIME-IMB].

      4. body id

         A string giving the content id as defined in [MIME-IMB].

      5. body description

         A string giving the content description as defined in
         [MIME-IMB].

      6. body encoding

         A string giving the content transfer encoding as defined in
         [MIME-IMB].

      7. body size

         A number giving the size of the body in octets.  Note that this size is
         the size in its transfer encoding and not the resulting size after any
         decoding.

    Put another way, the body structure is a list of seven elements.  The
    semantics of the elements of this list are:

       1. Byte string giving the major MIME type
       2. Byte string giving the minor MIME type
       3. A list giving the Content-Type parameters of the message
       4. A byte string giving the content identifier for the message part, or
          None if it has no content identifier.
       5. A byte string giving the content description for the message part, or
          None if it has no content description.
       6. A byte string giving the Content-Encoding of the message body
       7. An integer giving the number of octets in the message body

    The RFC goes on::

        Multiple parts are indicated by parenthesis nesting.  Instead of a body
        type as the first element of the parenthesized list, there is a sequence
        of one or more nested body structures.  The second element of the
        parenthesized list is the multipart subtype (mixed, digest, parallel,
        alternative, etc.).

        For example, a two part message consisting of a text and a
        BASE64-encoded text attachment can have a body structure of: (("TEXT"
        "PLAIN" ("CHARSET" "US-ASCII") NIL NIL "7BIT" 1152 23)("TEXT" "PLAIN"
        ("CHARSET" "US-ASCII" "NAME" "cc.diff")
        "<960723163407.20117h@cac.washington.edu>" "Compiler diff" "BASE64" 4554
        73) "MIXED")

    This is represented as::

        [["TEXT", "PLAIN", ["CHARSET", "US-ASCII"], None, None, "7BIT", 1152,
          23],
         ["TEXT", "PLAIN", ["CHARSET", "US-ASCII", "NAME", "cc.diff"],
          "<960723163407.20117h@cac.washington.edu>", "Compiler diff",
          "BASE64", 4554, 73],
         "MIXED"]

    In other words, a list of N + 1 elements, where N is the number of parts in
    the message.  The first N elements are structures as defined by the previous
    section.  The last element is the minor MIME subtype of the multipart
    message.

    Additionally, the RFC describes extension data::

        Extension data follows the multipart subtype.  Extension data is never
        returned with the BODY fetch, but can be returned with a BODYSTRUCTURE
        fetch.  Extension data, if present, MUST be in the defined order.

    The C{extended} flag controls whether extension data might be returned with
    the normal data.
    """
    return _getMessageStructure(msg).encode(extended)



class IMessagePart(Interface):
    def getHeaders(negate, *names):
        """Retrieve a group of message headers.

        @type names: C{tuple} of C{str}
        @param names: The names of the headers to retrieve or omit.

        @type negate: C{bool}
        @param negate: If True, indicates that the headers listed in C{names}
        should be omitted from the return value, rather than included.

        @rtype: C{dict}
        @return: A mapping of header field names to header field values
        """

    def getBodyFile():
        """Retrieve a file object containing only the body of this message.
        """

    def getSize():
        """Retrieve the total size, in octets, of this message.

        @rtype: C{int}
        """

    def isMultipart():
        """Indicate whether this message has subparts.

        @rtype: C{bool}
        """

    def getSubPart(part):
        """Retrieve a MIME sub-message

        @type part: C{int}
        @param part: The number of the part to retrieve, indexed from 0.

        @raise IndexError: Raised if the specified part does not exist.
        @raise TypeError: Raised if this message is not multipart.

        @rtype: Any object implementing C{IMessagePart}.
        @return: The specified sub-part.
        """

class IMessage(IMessagePart):
    def getUID():
        """Retrieve the unique identifier associated with this message.
        """

    def getFlags():
        """Retrieve the flags associated with this message.

        @rtype: C{iterable}
        @return: The flags, represented as strings.
        """

    def getInternalDate():
        """Retrieve the date internally associated with this message.

        @rtype: C{str}
        @return: An RFC822-formatted date string.
        """

class IMessageFile(Interface):
    """Optional message interface for representing messages as files.

    If provided by message objects, this interface will be used instead
    the more complex MIME-based interface.
    """
    def open():
        """Return an file-like object opened for reading.

        Reading from the returned file will return all the bytes
        of which this message consists.
        """

class ISearchableMailbox(Interface):
    def search(query, uid):
        """Search for messages that meet the given query criteria.

        If this interface is not implemented by the mailbox, L{IMailbox.fetch}
        and various methods of L{IMessage} will be used instead.

        Implementations which wish to offer better performance than the
        default implementation should implement this interface.

        @type query: C{list}
        @param query: The search criteria

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs;
        otherwise they are message sequence IDs.

        @rtype: C{list} or C{Deferred}
        @return: A list of message sequence numbers or message UIDs which
        match the search criteria or a C{Deferred} whose callback will be
        invoked with such a list.

        @raise IllegalQueryError: Raised when query is not valid.
        """

class IMessageCopier(Interface):
    def copy(messageObject):
        """Copy the given message object into this mailbox.

        The message object will be one which was previously returned by
        L{IMailbox.fetch}.

        Implementations which wish to offer better performance than the
        default implementation should implement this interface.

        If this interface is not implemented by the mailbox, IMailbox.addMessage
        will be used instead.

        @rtype: C{Deferred} or C{int}
        @return: Either the UID of the message or a Deferred which fires
        with the UID when the copy finishes.
        """

class IMailboxInfo(Interface):
    """Interface specifying only the methods required for C{listMailboxes}.

    Implementations can return objects implementing only these methods for
    return to C{listMailboxes} if it can allow them to operate more
    efficiently.
    """

    def getFlags():
        """Return the flags defined in this mailbox

        Flags with the \\ prefix are reserved for use as system flags.

        @rtype: C{list} of C{str}
        @return: A list of the flags that can be set on messages in this mailbox.
        """

    def getHierarchicalDelimiter():
        """Get the character which delimits namespaces for in this mailbox.

        @rtype: C{str}
        """

class IMailbox(IMailboxInfo):
    def getUIDValidity():
        """Return the unique validity identifier for this mailbox.

        @rtype: C{int}
        """

    def getUIDNext():
        """Return the likely UID for the next message added to this mailbox.

        @rtype: C{int}
        """

    def getUID(message):
        """Return the UID of a message in the mailbox

        @type message: C{int}
        @param message: The message sequence number

        @rtype: C{int}
        @return: The UID of the message.
        """

    def getMessageCount():
        """Return the number of messages in this mailbox.

        @rtype: C{int}
        """

    def getRecentCount():
        """Return the number of messages with the 'Recent' flag.

        @rtype: C{int}
        """

    def getUnseenCount():
        """Return the number of messages with the 'Unseen' flag.

        @rtype: C{int}
        """

    def isWriteable():
        """Get the read/write status of the mailbox.

        @rtype: C{int}
        @return: A true value if write permission is allowed, a false value otherwise.
        """

    def destroy():
        """Called before this mailbox is deleted, permanently.

        If necessary, all resources held by this mailbox should be cleaned
        up here.  This function _must_ set the \\Noselect flag on this
        mailbox.
        """

    def requestStatus(names):
        """Return status information about this mailbox.

        Mailboxes which do not intend to do any special processing to
        generate the return value, C{statusRequestHelper} can be used
        to build the dictionary by calling the other interface methods
        which return the data for each name.

        @type names: Any iterable
        @param names: The status names to return information regarding.
        The possible values for each name are: MESSAGES, RECENT, UIDNEXT,
        UIDVALIDITY, UNSEEN.

        @rtype: C{dict} or C{Deferred}
        @return: A dictionary containing status information about the
        requested names is returned.  If the process of looking this
        information up would be costly, a deferred whose callback will
        eventually be passed this dictionary is returned instead.
        """

    def addListener(listener):
        """Add a mailbox change listener

        @type listener: Any object which implements C{IMailboxListener}
        @param listener: An object to add to the set of those which will
        be notified when the contents of this mailbox change.
        """

    def removeListener(listener):
        """Remove a mailbox change listener

        @type listener: Any object previously added to and not removed from
        this mailbox as a listener.
        @param listener: The object to remove from the set of listeners.

        @raise ValueError: Raised when the given object is not a listener for
        this mailbox.
        """

    def addMessage(message, flags = (), date = None):
        """Add the given message to this mailbox.

        @type message: A file-like object
        @param message: The RFC822 formatted message

        @type flags: Any iterable of C{str}
        @param flags: The flags to associate with this message

        @type date: C{str}
        @param date: If specified, the date to associate with this
        message.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with the message
        id if the message is added successfully and whose errback is
        invoked otherwise.

        @raise ReadOnlyMailbox: Raised if this Mailbox is not open for
        read-write.
        """

    def expunge():
        """Remove all messages flagged \\Deleted.

        @rtype: C{list} or C{Deferred}
        @return: The list of message sequence numbers which were deleted,
        or a C{Deferred} whose callback will be invoked with such a list.

        @raise ReadOnlyMailbox: Raised if this Mailbox is not open for
        read-write.
        """

    def fetch(messages, uid):
        """Retrieve one or more messages.

        @type messages: C{MessageSet}
        @param messages: The identifiers of messages to retrieve information
        about

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs;
        otherwise they are message sequence IDs.

        @rtype: Any iterable of two-tuples of message sequence numbers and
        implementors of C{IMessage}.
        """

    def store(messages, flags, mode, uid):
        """Set the flags of one or more messages.

        @type messages: A MessageSet object with the list of messages requested
        @param messages: The identifiers of the messages to set the flags of.

        @type flags: sequence of C{str}
        @param flags: The flags to set, unset, or add.

        @type mode: -1, 0, or 1
        @param mode: If mode is -1, these flags should be removed from the
        specified messages.  If mode is 1, these flags should be added to
        the specified messages.  If mode is 0, all existing flags should be
        cleared and these flags should be added.

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs;
        otherwise they are message sequence IDs.

        @rtype: C{dict} or C{Deferred}
        @return: A C{dict} mapping message sequence numbers to sequences of C{str}
        representing the flags set on the message after this operation has
        been performed, or a C{Deferred} whose callback will be invoked with
        such a C{dict}.

        @raise ReadOnlyMailbox: Raised if this mailbox is not open for
        read-write.
        """

class ICloseableMailbox(Interface):
    """A supplementary interface for mailboxes which require cleanup on close.

    Implementing this interface is optional.  If it is implemented, the protocol
    code will call the close method defined whenever a mailbox is closed.
    """
    def close():
        """Close this mailbox.

        @return: A C{Deferred} which fires when this mailbox
        has been closed, or None if the mailbox can be closed
        immediately.
        """

def _formatHeaders(headers):
    hdrs = [': '.join((k.title(), '\r\n'.join(v.splitlines()))) for (k, v)
            in headers.iteritems()]
    hdrs = '\r\n'.join(hdrs) + '\r\n'
    return hdrs

def subparts(m):
    i = 0
    try:
        while True:
            yield m.getSubPart(i)
            i += 1
    except IndexError:
        pass

def iterateInReactor(i):
    """Consume an interator at most a single iteration per reactor iteration.

    If the iterator produces a Deferred, the next iteration will not occur
    until the Deferred fires, otherwise the next iteration will be taken
    in the next reactor iteration.

    @rtype: C{Deferred}
    @return: A deferred which fires (with None) when the iterator is
    exhausted or whose errback is called if there is an exception.
    """
    from twisted.internet import reactor
    d = defer.Deferred()
    def go(last):
        try:
            r = i.next()
        except StopIteration:
            d.callback(last)
        except:
            d.errback()
        else:
            if isinstance(r, defer.Deferred):
                r.addCallback(go)
            else:
                reactor.callLater(0, go, r)
    go(None)
    return d

class MessageProducer:
    CHUNK_SIZE = 2 ** 2 ** 2 ** 2

    def __init__(self, msg, buffer = None, scheduler = None):
        """Produce this message.

        @param msg: The message I am to produce.
        @type msg: L{IMessage}

        @param buffer: A buffer to hold the message in.  If None, I will
            use a L{tempfile.TemporaryFile}.
        @type buffer: file-like
        """
        self.msg = msg
        if buffer is None:
            buffer = tempfile.TemporaryFile()
        self.buffer = buffer
        if scheduler is None:
            scheduler = iterateInReactor
        self.scheduler = scheduler
        self.write = self.buffer.write

    def beginProducing(self, consumer):
        self.consumer = consumer
        return self.scheduler(self._produce())

    def _produce(self):
        headers = self.msg.getHeaders(True)
        boundary = None
        if self.msg.isMultipart():
            content = headers.get('content-type')
            parts = [x.split('=', 1) for x in content.split(';')[1:]]
            parts = dict([(k.lower().strip(), v) for (k, v) in parts])
            boundary = parts.get('boundary')
            if boundary is None:
                # Bastards
                boundary = '----=_%f_boundary_%f' % (time.time(), random.random())
                headers['content-type'] += '; boundary="%s"' % (boundary,)
            else:
                if boundary.startswith('"') and boundary.endswith('"'):
                    boundary = boundary[1:-1]

        self.write(_formatHeaders(headers))
        self.write('\r\n')
        if self.msg.isMultipart():
            for p in subparts(self.msg):
                self.write('\r\n--%s\r\n' % (boundary,))
                yield MessageProducer(p, self.buffer, self.scheduler
                    ).beginProducing(None
                    )
            self.write('\r\n--%s--\r\n' % (boundary,))
        else:
            f = self.msg.getBodyFile()
            while True:
                b = f.read(self.CHUNK_SIZE)
                if b:
                    self.buffer.write(b)
                    yield None
                else:
                    break
        if self.consumer:
            self.buffer.seek(0, 0)
            yield FileProducer(self.buffer
                ).beginProducing(self.consumer
                ).addCallback(lambda _: self
                )

class _FetchParser:
    class Envelope:
        # Response should be a list of fields from the message:
        #   date, subject, from, sender, reply-to, to, cc, bcc, in-reply-to,
        #   and message-id.
        #
        # from, sender, reply-to, to, cc, and bcc are themselves lists of
        # address information:
        #   personal name, source route, mailbox name, host name
        #
        # reply-to and sender must not be None.  If not present in a message
        # they should be defaulted to the value of the from field.
        type = 'envelope'
        __str__ = lambda self: 'envelope'

    class Flags:
        type = 'flags'
        __str__ = lambda self: 'flags'

    class InternalDate:
        type = 'internaldate'
        __str__ = lambda self: 'internaldate'

    class RFC822Header:
        type = 'rfc822header'
        __str__ = lambda self: 'rfc822.header'

    class RFC822Text:
        type = 'rfc822text'
        __str__ = lambda self: 'rfc822.text'

    class RFC822Size:
        type = 'rfc822size'
        __str__ = lambda self: 'rfc822.size'

    class RFC822:
        type = 'rfc822'
        __str__ = lambda self: 'rfc822'

    class UID:
        type = 'uid'
        __str__ = lambda self: 'uid'

    class Body:
        type = 'body'
        peek = False
        header = None
        mime = None
        text = None
        part = ()
        empty = False
        partialBegin = None
        partialLength = None
        def __str__(self):
            base = 'BODY'
            part = ''
            separator = ''
            if self.part:
                part = '.'.join([str(x + 1) for x in self.part])
                separator = '.'
#            if self.peek:
#                base += '.PEEK'
            if self.header:
                base += '[%s%s%s]' % (part, separator, self.header,)
            elif self.text:
                base += '[%s%sTEXT]' % (part, separator)
            elif self.mime:
                base += '[%s%sMIME]' % (part, separator)
            elif self.empty:
                base += '[%s]' % (part,)
            if self.partialBegin is not None:
                base += '<%d.%d>' % (self.partialBegin, self.partialLength)
            return base

    class BodyStructure:
        type = 'bodystructure'
        __str__ = lambda self: 'bodystructure'

    # These three aren't top-level, they don't need type indicators
    class Header:
        negate = False
        fields = None
        part = None
        def __str__(self):
            base = 'HEADER'
            if self.fields:
                base += '.FIELDS'
                if self.negate:
                    base += '.NOT'
                fields = []
                for f in self.fields:
                    f = f.title()
                    if _needsQuote(f):
                        f = _quote(f)
                    fields.append(f)
                base += ' (%s)' % ' '.join(fields)
            if self.part:
                base = '.'.join([str(x + 1) for x in self.part]) + '.' + base
            return base

    class Text:
        pass

    class MIME:
        pass

    parts = None

    _simple_fetch_att = [
        ('envelope', Envelope),
        ('flags', Flags),
        ('internaldate', InternalDate),
        ('rfc822.header', RFC822Header),
        ('rfc822.text', RFC822Text),
        ('rfc822.size', RFC822Size),
        ('rfc822', RFC822),
        ('uid', UID),
        ('bodystructure', BodyStructure),
    ]

    def __init__(self):
        self.state = ['initial']
        self.result = []
        self.remaining = ''

    def parseString(self, s):
        s = self.remaining + s
        try:
            while s or self.state:
                if not self.state:
                    raise IllegalClientResponse("Invalid Argument")
                # print 'Entering state_' + self.state[-1] + ' with', repr(s)
                state = self.state.pop()
                try:
                    used = getattr(self, 'state_' + state)(s)
                except:
                    self.state.append(state)
                    raise
                else:
                    # print state, 'consumed', repr(s[:used])
                    s = s[used:]
        finally:
            self.remaining = s

    def state_initial(self, s):
        # In the initial state, the literals "ALL", "FULL", and "FAST"
        # are accepted, as is a ( indicating the beginning of a fetch_att
        # token, as is the beginning of a fetch_att token.
        if s == '':
            return 0

        l = s.lower()
        if l.startswith('all'):
            self.result.extend((
                self.Flags(), self.InternalDate(),
                self.RFC822Size(), self.Envelope()
            ))
            return 3
        if l.startswith('full'):
            self.result.extend((
                self.Flags(), self.InternalDate(),
                self.RFC822Size(), self.Envelope(),
                self.Body()
            ))
            return 4
        if l.startswith('fast'):
            self.result.extend((
                self.Flags(), self.InternalDate(), self.RFC822Size(),
            ))
            return 4

        if l.startswith('('):
            self.state.extend(('close_paren', 'maybe_fetch_att', 'fetch_att'))
            return 1

        self.state.append('fetch_att')
        return 0

    def state_close_paren(self, s):
        if s.startswith(')'):
            return 1
        raise Exception("Missing )")

    def state_whitespace(self, s):
        # Eat up all the leading whitespace
        if not s or not s[0].isspace():
            raise Exception("Whitespace expected, none found")
        i = 0
        for i in range(len(s)):
            if not s[i].isspace():
                break
        return i

    def state_maybe_fetch_att(self, s):
        if not s.startswith(')'):
            self.state.extend(('maybe_fetch_att', 'fetch_att', 'whitespace'))
        return 0

    def state_fetch_att(self, s):
        # Allowed fetch_att tokens are "ENVELOPE", "FLAGS", "INTERNALDATE",
        # "RFC822", "RFC822.HEADER", "RFC822.SIZE", "RFC822.TEXT", "BODY",
        # "BODYSTRUCTURE", "UID",
        # "BODY [".PEEK"] [<section>] ["<" <number> "." <nz_number> ">"]

        l = s.lower()
        for (name, cls) in self._simple_fetch_att:
            if l.startswith(name):
                self.result.append(cls())
                return len(name)

        b = self.Body()
        if l.startswith('body.peek'):
            b.peek = True
            used = 9
        elif l.startswith('body'):
            used = 4
        else:
            raise Exception("Nothing recognized in fetch_att: %s" % (l,))

        self.pending_body = b
        self.state.extend(('got_body', 'maybe_partial', 'maybe_section'))
        return used

    def state_got_body(self, s):
        self.result.append(self.pending_body)
        del self.pending_body
        return 0

    def state_maybe_section(self, s):
        if not s.startswith("["):
            return 0

        self.state.extend(('section', 'part_number'))
        return 1

    _partExpr = re.compile(r'(\d+(?:\.\d+)*)\.?')
    def state_part_number(self, s):
        m = self._partExpr.match(s)
        if m is not None:
            self.parts = [int(p) - 1 for p in m.groups()[0].split('.')]
            return m.end()
        else:
            self.parts = []
            return 0

    def state_section(self, s):
        # Grab "HEADER]" or "HEADER.FIELDS (Header list)]" or
        # "HEADER.FIELDS.NOT (Header list)]" or "TEXT]" or "MIME]" or
        # just "]".

        l = s.lower()
        used = 0
        if l.startswith(']'):
            self.pending_body.empty = True
            used += 1
        elif l.startswith('header]'):
            h = self.pending_body.header = self.Header()
            h.negate = True
            h.fields = ()
            used += 7
        elif l.startswith('text]'):
            self.pending_body.text = self.Text()
            used += 5
        elif l.startswith('mime]'):
            self.pending_body.mime = self.MIME()
            used += 5
        else:
            h = self.Header()
            if l.startswith('header.fields.not'):
                h.negate = True
                used += 17
            elif l.startswith('header.fields'):
                used += 13
            else:
                raise Exception("Unhandled section contents: %r" % (l,))

            self.pending_body.header = h
            self.state.extend(('finish_section', 'header_list', 'whitespace'))
        self.pending_body.part = tuple(self.parts)
        self.parts = None
        return used

    def state_finish_section(self, s):
        if not s.startswith(']'):
            raise Exception("section must end with ]")
        return 1

    def state_header_list(self, s):
        if not s.startswith('('):
            raise Exception("Header list must begin with (")
        end = s.find(')')
        if end == -1:
            raise Exception("Header list must end with )")

        headers = s[1:end].split()
        self.pending_body.header.fields = map(str.upper, headers)
        return end + 1

    def state_maybe_partial(self, s):
        # Grab <number.number> or nothing at all
        if not s.startswith('<'):
            return 0
        end = s.find('>')
        if end == -1:
            raise Exception("Found < but not >")

        partial = s[1:end]
        parts = partial.split('.', 1)
        if len(parts) != 2:
            raise Exception("Partial specification did not include two .-delimited integers")
        begin, length = map(int, parts)
        self.pending_body.partialBegin = begin
        self.pending_body.partialLength = length

        return end + 1

class FileProducer:
    CHUNK_SIZE = 2 ** 2 ** 2 ** 2

    firstWrite = True

    def __init__(self, f):
        self.f = f

    def beginProducing(self, consumer):
        self.consumer = consumer
        self.produce = consumer.write
        d = self._onDone = defer.Deferred()
        self.consumer.registerProducer(self, False)
        return d

    def resumeProducing(self):
        b = ''
        if self.firstWrite:
            b = '{%d}\r\n' % self._size()
            self.firstWrite = False
        if not self.f:
            return
        b = b + self.f.read(self.CHUNK_SIZE)
        if not b:
            self.consumer.unregisterProducer()
            self._onDone.callback(self)
            self._onDone = self.f = self.consumer = None
        else:
            self.produce(b)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

    def _size(self):
        b = self.f.tell()
        self.f.seek(0, 2)
        e = self.f.tell()
        self.f.seek(b, 0)
        return e - b

def parseTime(s):
    # XXX - This may require localization :(
    months = [
        'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct',
        'nov', 'dec', 'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december'
    ]
    expr = {
        'day': r"(?P<day>3[0-1]|[1-2]\d|0[1-9]|[1-9]| [1-9])",
        'mon': r"(?P<mon>\w+)",
        'year': r"(?P<year>\d\d\d\d)"
    }
    m = re.match('%(day)s-%(mon)s-%(year)s' % expr, s)
    if not m:
        raise ValueError, "Cannot parse time string %r" % (s,)
    d = m.groupdict()
    try:
        d['mon'] = 1 + (months.index(d['mon'].lower()) % 12)
        d['year'] = int(d['year'])
        d['day'] = int(d['day'])
    except ValueError:
        raise ValueError, "Cannot parse time string %r" % (s,)
    else:
        return time.struct_time(
            (d['year'], d['mon'], d['day'], 0, 0, 0, -1, -1, -1)
        )

import codecs
def modified_base64(s):
    s_utf7 = s.encode('utf-7')
    return s_utf7[1:-1].replace('/', ',')

def modified_unbase64(s):
    s_utf7 = '+' + s.replace(',', '/') + '-'
    return s_utf7.decode('utf-7')

def encoder(s, errors=None):
    """
    Encode the given C{unicode} string using the IMAP4 specific variation of
    UTF-7.

    @type s: C{unicode}
    @param s: The text to encode.

    @param errors: Policy for handling encoding errors.  Currently ignored.

    @return: C{tuple} of a C{str} giving the encoded bytes and an C{int}
        giving the number of code units consumed from the input.
    """
    r = []
    _in = []
    for c in s:
        if ord(c) in (range(0x20, 0x26) + range(0x27, 0x7f)):
            if _in:
                r.extend(['&', modified_base64(''.join(_in)), '-'])
                del _in[:]
            r.append(str(c))
        elif c == '&':
            if _in:
                r.extend(['&', modified_base64(''.join(_in)), '-'])
                del _in[:]
            r.append('&-')
        else:
            _in.append(c)
    if _in:
        r.extend(['&', modified_base64(''.join(_in)), '-'])
    return (''.join(r), len(s))

def decoder(s, errors=None):
    """
    Decode the given C{str} using the IMAP4 specific variation of UTF-7.

    @type s: C{str}
    @param s: The bytes to decode.

    @param errors: Policy for handling decoding errors.  Currently ignored.

    @return: a C{tuple} of a C{unicode} string giving the text which was
        decoded and an C{int} giving the number of bytes consumed from the
        input.
    """
    r = []
    decode = []
    for c in s:
        if c == '&' and not decode:
            decode.append('&')
        elif c == '-' and decode:
            if len(decode) == 1:
                r.append('&')
            else:
                r.append(modified_unbase64(''.join(decode[1:])))
            decode = []
        elif decode:
            decode.append(c)
        else:
            r.append(c)
    if decode:
        r.append(modified_unbase64(''.join(decode[1:])))
    return (''.join(r), len(s))

class StreamReader(codecs.StreamReader):
    def decode(self, s, errors='strict'):
        return decoder(s)

class StreamWriter(codecs.StreamWriter):
    def encode(self, s, errors='strict'):
        return encoder(s)

_codecInfo = (encoder, decoder, StreamReader, StreamWriter)
try:
    _codecInfoClass = codecs.CodecInfo
except AttributeError:
    pass
else:
    _codecInfo = _codecInfoClass(*_codecInfo)

def imap4_utf_7(name):
    if name == 'imap4-utf-7':
        return _codecInfo
codecs.register(imap4_utf_7)

__all__ = [
    # Protocol classes
    'IMAP4Server', 'IMAP4Client',

    # Interfaces
    'IMailboxListener', 'IClientAuthentication', 'IAccount', 'IMailbox',
    'INamespacePresenter', 'ICloseableMailbox', 'IMailboxInfo',
    'IMessage', 'IMessageCopier', 'IMessageFile', 'ISearchableMailbox',

    # Exceptions
    'IMAP4Exception', 'IllegalClientResponse', 'IllegalOperation',
    'IllegalMailboxEncoding', 'UnhandledResponse', 'NegativeResponse',
    'NoSupportedAuthentication', 'IllegalServerResponse',
    'IllegalIdentifierError', 'IllegalQueryError', 'MismatchedNesting',
    'MismatchedQuoting', 'MailboxException', 'MailboxCollision',
    'NoSuchMailbox', 'ReadOnlyMailbox',

    # Auth objects
    'CramMD5ClientAuthenticator', 'PLAINAuthenticator', 'LOGINAuthenticator',
    'PLAINCredentials', 'LOGINCredentials',

    # Simple query interface
    'Query', 'Not', 'Or',

    # Miscellaneous
    'MemoryAccount',
    'statusRequestHelper',
]
