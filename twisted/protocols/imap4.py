# -*- test-case-name: twisted.test.test_imap -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
An IMAP4 protocol implementation

API Stability: Semi-stable

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}

To do: 
  Suspend idle timeout while server is processing
  Use an async message parser instead of buffering in memory
  Figure out a way to not queue multi-message client requests (Flow? A simple callback?)
  Clarify some API docs (Query, etc)
"""

from __future__ import nested_scopes
from __future__ import generators

from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import defer
from twisted.internet.defer import maybeDeferred
from twisted.python import log, components, util, failure
from twisted.cred import perspective
from twisted.python.components import implements
from twisted.internet.interfaces import ITLSTransport

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials

import base64
import binascii
import operator
import re
import string
import time
import types
import rfc822
import random
import sys

try:
    import cStringIO as StringIO
except:
    import StringIO

class MessageSet:
    def __init__(self, *ranges):
        assert len(ranges) % 2 == 0, "Arguments must be low-high pairs"
        self.ranges = ranges
    
    def _rangePairs(self):
        return zip(*[iter(self.ranges)] * 2)

    def __add__(self, other):
        if isinstance(other, MessageSet):
            ranges = self.ranges + other.ranges
        else:
            ranges = list(self.ranges) + list(other)
        return MessageSet(*ranges)
    
    def __contains__(self, value):
        for (low, high) in self._rangePairs():
            if (low is None or value >= low) and (high is None or value <= high):
                return True
        return False
    
    def transform(self, callable):
        new = []
        for e in self.ranges:
            if e is None:
                new.append(None)
            else:
                new.append(callable(e))
        return MessageSet(*new)
    
    def __eq__(self, other):
        if isinstance(other, MessageSet):
            return self.ranges == other.ranges
        return False
    
    def __len__(self):
        if self.ranges:
            if self.ranges[-1] is None:
                return sys.maxint
            L = 0
            for (low, high) in self._rangePairs():
                L = L + high - low + 1
            return L
        return 0
    
    def __iter__(self):
        def i():
            for (low, high) in self._rangePairs():
                while high is None or low <= high:
                    yield low
                    low += 1
        return i()
    
    def __str__(self):
        p = []
        for (low, high) in self._rangePairs():
            if low == high:
                p.append(str(low))
            elif high is None:
                p.append('%d:*' % (low,))
            else:
                p.append('%d:%d' % (low, high))
        return ','.join(p)
    
    def __repr__(self):
        return '<MessageSet %s>' % (str(self),)

class Command:
    _1_RESPONSES = ('CAPABILITY', 'FLAGS', 'LIST', 'LSUB', 'STATUS', 'SEARCH')
    _2_RESPONSES = ('EXISTS', 'EXPUNGE', 'FETCH', 'RECENT')
    _OK_RESPONSES = ('UIDVALIDITY', 'READ-WRITE', 'READ-ONLY')
    defer = None
    
    def __init__(self, command, args='', continuation=None, wantResponse=()):
        self.command = command
        self.args = args
        self.continuation = continuation
        self.wantResponse = wantResponse
        self.lines = []
    
    def finish(self, lastLine, unusedCallback):
        send = []
        unuse = []
        for L in self.lines:
            names = parseNestedParens(L)
            N = len(names)
            if (N >= 1 and names[0] in self._1_RESPONSES or
                N >= 2 and names[1] in self._2_RESPONSES or
                N >= 2 and names[0] == 'OK' and isinstance(names[1], types.ListType) and names[1][0] in self._OK_RESPONSES):
                send.append(L)
            else:
                unuse.append(L)
        self.defer.callback((send, lastLine))
        if unuse:
            unusedCallback(unuse)

class IMAP4Exception(Exception):
    def __init__(self, *args):
        Exception.__init__(self, *args)

class IllegalClientResponse(IMAP4Exception): pass

class IllegalOperation(IMAP4Exception): pass

class IllegalMailboxEncoding(IMAP4Exception): pass

class IMailboxListener(components.Interface):
    """Interface for objects interested in mailbox events"""
    
    def modeChanged(self, writeable):
        """Indicates that the write status of a mailbox has changed.
        
        @type writeable: C{bool}
        @param writeable: A true value if write is now allowed, false
        otherwise.
        """
    
    def flagsChanged(self, newFlags):
        """Indicates that the flags of one or more messages have changed.
        
        @type newFlags: C{dict}
        @param newFlags: A mapping of message identifiers to tuples of flags
        new set on that message.
        """

    def newMessages(self, exists, recent):
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
    __implements__ = (IMailboxListener,)

    # Capabilities supported by this server
    CAPABILITIES = None

    # Identifier for this server software
    IDENT = 'Twisted IMAP4rev1 Ready'
    
    # Number of seconds before idle timeout
    # Initially 1 minute.  Raised to 30 minutes after login.
    timeOut = 60

    POSTAUTH_TIMEOUT = 60 * 30

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

    _memoryFileLimit = 1024 * 1024 * 10

    # Command data to be processed when literal data is received
    _pendingLiteral = None
    _pendingBuffer = None
    _pendingSize = None

    # Challenge generators for AUTHENTICATE command
    challengers = None
    
    state = 'unauth'

    def __init__(self, chal = None, contextFactory = None):
        if chal is None:
            chal = []
        self.challengers = dict([(c.getName().upper(), c) for c in chal])
        self.challengers = {}
        self.CAPABILITIES = {'AUTH': self.challengers.keys()}
        self.ctx = contextFactory

    def connectionMade(self):
        self.setTimeout(self.timeOut)

        if self.ctx and implements(self.transport, ITLSTransport):
            self.CAPABILITIES['LOGINDISABLED'] = None
            self.CAPABILITIES['STARTTLS'] = None
        
        self.tags = {}
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

    def rawDataReceived(self, data):
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
            callback = self._pendingLiteral.callback
            self._pendingLiteral = None
            rest.seek(0, 0)
            callback(rest)
            self.setLineMode(passon.lstrip('\r\n'))

    def lineReceived(self, line):
        # print 'S: ' + line.replace('\r', '\\r')
        self.resetTimeout()

        args = line.split(None, 2)
        rest = None
        if self._pendingLiteral:
            d = self._pendingLiteral
            self._pendingLiteral = None
            d.callback(line)
            return
        elif len(args) == 3:
            tag, cmd, rest = args
        elif len(args) == 2:
            tag, cmd = args
        else:
            # XXX - This is rude.
            self.transport.loseConnection()
            # raise IllegalClientResponse(line)

        cmd = cmd.upper()
        self.dispatchCommand(tag, cmd, rest)

    def dispatchCommand(self, tag, cmd, rest):
        f = self.lookupCommand(cmd)
        if f:
            try:
                f(tag, rest)
            except IllegalClientResponse, e:
                self.sendBadResponse(tag, 'Illegal syntax: ' + str(e))
            except IllegalOperation, e:
                self.sendNegativeResponse(tag, 'Illegal operation: ' + str(e))
            except IllegalMailboxEncoding, e:
                self.sendNegativeResponse(tag, 'Illegal mailbox name: ' + str(e))
            except Exception, e:
                self.sendBadResponse(tag, 'Server error: ' + str(e))
                log.err()
        else:
            self.sendBadResponse(tag, 'Unsupported command')

    def lookupCommand(self, cmd):
        return getattr(self, '_'.join((self.state, cmd.upper())), None)

    def sendServerGreeting(self):
        msg = '[CAPABILITY %s] %s' % (' '.join(self.listCapabilities()), self.IDENT)
        self.sendPositiveResponse(message=msg)

    def sendBadResponse(self, tag = None, message = ''):
        self._respond('BAD', tag, message)

    def sendPositiveResponse(self, tag = None, message = ''):
        self._respond('OK', tag, message)

    def sendNegativeResponse(self, tag = None, message = ''):
        self._respond('NO', tag, message)

    def sendUntaggedResponse(self, message):
        self._respond(message, None, None)

    def sendContinuationRequest(self, msg = 'Ready for additional command text'):
        self.sendLine('+ ' + msg)

    def _setupForLiteral(self, octets):
        self._pendingBuffer = self.messageFile(octets)
        self._pendingSize = octets
        self._pendingLiteral = defer.Deferred()
        self.sendContinuationRequest('Ready for %d octets of text' % octets)
        self.setRawMode()
        return self._pendingLiteral
    
    def messageFile(self, octets):
        """Create a file to which an incoming message may be written.
        
        @type octets: C{int}
        @param octets: The number of octets which will be written to the file
        
        @rtype: Any object which implements C{write(string)} and
        C{seek(int, int)}
        @return: A file-like object
        """
        if octets > self._memoryFileLimit:
            return tempfile.TemproraryFile()
        else:
            return StringIO.StringIO()

    def _respond(self, state, tag, message):
        if not tag:
            tag = '*'
        if message:
            self.sendLine(' '.join((tag, state, message)))
        else:
            self.sendLine(' '.join((tag, state)))

    def listCapabilities(self):
        caps = ['IMAP4rev1']
        for c, v in self.CAPABILITIES.items():
            if v is None:
                caps.append(c)
            elif len(v):
                caps.extend([('%s=%s' % (c, cap)) for cap in v])
        return caps

    def unauth_CAPABILITY(self, tag, args):
        self.sendUntaggedResponse('CAPABILITY ' + ' '.join(self.listCapabilities()))
        self.sendPositiveResponse(tag, 'CAPABILITY completed')

    auth_CAPABILITY = unauth_CAPABILITY
    select_CAPABILITY = unauth_CAPABILITY
    logout_CAPABILITY = unauth_CAPABILITY

    def unauth_LOGOUT(self, tag, args):
        self.sendUntaggedResponse('BYE Nice talking to you')
        self.sendPositiveResponse(tag, 'LOGOUT successful')
        self.transport.loseConnection()

    auth_LOGOUT = unauth_LOGOUT
    select_LOGOUT = unauth_LOGOUT
    logout_LOGOUT = unauth_LOGOUT

    def unauth_QUIT(self, tag, args):
        self.sendUntaggedResponse('BYE The correct way to terminate a session is LOGOUT')
        self.sendPositiveResponse(tag, 'QUIT successful')
        self.transport.loseConnection()

    auth_QUIT = unauth_QUIT
    select_QUIT = unauth_QUIT
    logout_QUIT = unauth_QUIT

    def unauth_NOOP(self, tag, args):
        self.sendPositiveResponse(tag, 'NOOP No operation performed')

    auth_NOOP = unauth_NOOP
    select_NOOP = unauth_NOOP
    logout_NOOP = unauth_NOOP

    def unauth_AUTHENTICATE(self, tag, args):
        args = args.upper().strip()
        if args not in self.challengers:
            self.sendNegativeResponse(tag, 'AUTHENTICATE method unsupported')
        else:
            self.authenticate(self.challengers[args](), tag)

    def authenticate(self, chal, tag):
        if self.portal is None:
            self.sendNegativeResponse(tag, 'Temporary authentication failure')
            return

        try:
            challenge = chal.getChallenge()
        except Exception, e:
            self.sendBadResponse(tag, 'Server error: ' + str(e))
            chal.abort()
        else:
            coded = base64.encodestring(challenge)[:-1]
            self._pendingLiteral = defer.Deferred()
            self.sendContinuationRequest(coded)
            self._pendingLiteral.addCallback(self.__cbAuthChunk, chal, tag)
            self._pendingLiteral.addErrback(self.__ebAuthChunk, chal, tag)

    def __cbAuthChunk(self, result, chal, tag):
        try:
            uncoded = base64.decodestring(result)
        except binascii.Error:
            chal.abort()
            raise error.Unauthorized, "Malformed Response - not base64"

        chal.setResponse(uncoded)
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
            self.sendNegativeResponse(tag, 'Authentication failed: ' + str(failure.value))
        else:
            self.sendBadResponse(tag, 'Server error')
            log.err(failure)
    
    def __ebAuthChunk(self, auth, failure, tag):
        self.sendNegativeResponse(tag, 'Authentication failed: ' + str(failure.value))
        auth.abort()

    def unauth_STARTTLS(self, tag, args):
        if self.ctx and implements(self.transport, ITLSTransport):
            self.sendPositiveResponse(tag, 'Begin TLS negotiation now')
            self.transport.startTLS(self.ctx)
            del self.CAPABILITIES['LOGINDISABLED']
            del self.CAPABILITIES['STARTTLS']

    def unauth_LOGIN(self, tag, args):
        if 'LOGINDISABLED' in self.CAPABILITIES:
            self.sendBadResponse(tag, 'LOGIN is disabled before STARTTLS')
            return

        args = parseNestedParens(args)
        if len(args) != 2:
            self.sendBadResponse(tag, 'Wrong number of arguments')
        else:
            maybeDeferred(self.authenticateLogin, *args).addCallbacks(
                self.__cbLogin, self.__ebLogin, (tag,), None, (tag,), None
            )

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
            self.sendBadResponse(tag, 'Server error')
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

    def _parseMbox(self, name):
        try:
            # XXX - Piece of *crap* 2.1
            return decoder(splitQuoted(name)[0])[0]
        except:
            raise IllegalMailboxEncoding, name

    def _selectWork(self, tag, args, rw, cmdName):
        name = self._parseMbox(args)
        mbox = self.account.select(name, rw)
        
        if mbox is None:
            self.sendNegativeResponse(tag, 'No such mailbox')
            return

        self.state = 'select'
        flags = mbox.getFlags()
        self.sendUntaggedResponse(str(mbox.getMessageCount()) + ' EXISTS')
        self.sendUntaggedResponse(str(mbox.getRecentCount()) + ' RECENT')
        self.sendUntaggedResponse('FLAGS (%s)' % ' '.join(flags))
        self.sendPositiveResponse(None, '[UIDVALIDITY %d]' % mbox.getUIDValidity())

        s = mbox.isWriteable() and 'READ-WRITE' or 'READ-ONLY'

        if self.mbox:
            self.mbox.removeListener(self)
        self.mbox = mbox
        self.mbox.addListener(self)
        self.sendPositiveResponse(tag, '[%s] %s successful' % (s, cmdName))

    def auth_SELECT(self, tag, args):
        self._selectWork(tag, args, 1, 'SELECT')
    select_SELECT = auth_SELECT
    
    def auth_EXAMINE(self, tag, args):
        self._selectWork(tag, args, 0, 'EXAMINE')
    select_EXAMINE = auth_EXAMINE

    def auth_CREATE(self, tag, args):
        name = self._parseMbox(args)
        try:
            self.account.create(name)
        except MailboxCollision, c:
            self.sendNegativeResponse(tag, str(c))
        else:
            self.sendPositiveResponse(tag, 'Mailbox created')
    select_CREATE = auth_CREATE

    def auth_DELETE(self, tag, args):
        name = self._parseMbox(args)
        try:
            self.account.delete(name)
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Mailbox deleted')
    select_DELETE = auth_DELETE

    def auth_RENAME(self, tag, args):
        names = splitQuoted(args)
        if len(names) != 2:
            raise IllegalClientResponse, args
        oldname, newname = [self._parseMbox(n) for n in names]
        try:
            self.account.rename(oldname, newname)
        except TypeError:
            self.sendBadResponse(tag, 'Invalid command syntax')
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Mailbox renamed')
    select_RENAME = auth_RENAME

    def auth_SUBSCRIBE(self, tag, args):
        name = self._parseMbox(args)
        try:
            self.account.subscribe(name)
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Subscribed')
    select_SUBSCRIBE= auth_SUBSCRIBE

    def auth_UNSUBSCRIBE(self, tag, args):
        name = self._parseMbox(args)
        try:
            self.account.unsubscribe(name)
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Unsubscribed')
    select_UNSUBSCRIBE = auth_UNSUBSCRIBE

    def _listWork(self, tag, args, sub, cmdName):
        parts = splitQuoted(args)
        if len(parts) != 2:
            self.sendBadResponse(tag, 'Incorrect usage')
        else:
            ref = parts[0]
            mbox = self._parseMbox(parts[1])
            mailboxes = self.account.listMailboxes(ref, mbox)
            for (name, box) in mailboxes:
                if not sub or self.account.isSubscribed(name):
                    flags = '(%s)' % ' '.join(box.getFlags())
                    delim = box.getHierarchicalDelimiter()
                    self.sendUntaggedResponse('%s %s "%s" %s' % (cmdName, flags, delim, name))
            self.sendPositiveResponse(tag, '%s completed' % (cmdName,))

    def auth_LIST(self, tag, args):
        self._listWork(tag, args, 0, 'LIST')
    select_LIST = auth_LIST

    def auth_LSUB(self, tag, args):
        self._listWork(tag, args, 1, 'LSUB')
    select_LSUB = auth_LSUB

    def auth_STATUS(self, tag, args):
        names = parseNestedParens(args)
        if len(names) != 2:
            raise IllegalClientResponse(args)
        mailbox = self._parseMbox(names[0])
        names = names[1]
        mbox = self.account.select(mailbox, 0)
        if mbox:
            maybeDeferred(mbox.requestStatus, names).addCallbacks(
                self.__cbStatus, self.__ebStatus,
                (tag, mailbox), None, (tag, mailbox), None
            )
        else:
            self.sendNegativeResponse(tag, "Could not open mailbox")
    select_STATUS = auth_STATUS

    def __cbStatus(self, status, tag, box):
        line = ' '.join(['%s %s' % x for x in status.items()])
        self.sendUntaggedResponse('STATUS %s (%s)' % (box, line))
        self.sendPositiveResponse(tag, 'STATUS complete')

    def __ebStatus(self, failure, tag, box):
        self.sendBadResponse(tag, 'STATUS %s failed: %s' % (box, failure))

    def auth_APPEND(self, tag, args):
        parts = parseNestedParens(args, 0)
        if len(parts) == 2:
            flags = ()
            date = rfc822.formatdate()
            size = parts[1]
        elif len(parts) == 3:
            if isinstance(parts[1], list):
                flags = parts[1]
                date = rfc822.formatdate()
            else:
                flags = ()
                date = parts[1]
            size = parts[2]
        elif len(parts) ==  4:
            flags = parts[1]
            date = parts[2]
            size = parts[3]
        else:
            raise IllegalClientResponse, args

        if not size.startswith('{') or not size.endswith('}'):
            raise IllegalClientResponse, args
        try:
            size = int(size[1:-1])
        except ValueError:
            raise IllegalClientResponse, args

        mbox = self.account.select(parts[0])
        if not mbox:
            self.sendNegativeResponse(tag, '[TRYCREATE] No such mailbox')
        d = self._setupForLiteral(size)
        d.addCallback(self.__cbContinueAppend, tag, mbox, flags, date)
        d.addErrback(self.__ebAppend, tag)
    select_APPEND = auth_APPEND

    def __cbContinueAppend(self, rest, tag, mbox, flags, date):
        d = mbox.addMessage(rest, flags, date)
        d.addCallback(self.__cbAppend, tag, mbox)
        d.addErrback(self.__ebAppend, tag)

    def __cbAppend(self, result, tag, mbox):
        self.sendUntaggedResponse('%d EXISTS' % mbox.getMessageCount())
        self.sendPositiveResponse(tag, 'APPEND complete')

    def __ebAppend(self, failure, tag):
        self.sendBadResponse(tag, 'APPEND failed: ' + str(failure.value))

    def select_CHECK(self, tag, args):
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

    def select_CLOSE(self, tag, args):
        if self.mbox.isWriteable():
            maybeDeferred(self.mbox.expunge).addCallbacks(
                self.__cbClose, self.__ebClose, (tag,), None, (tag,), None
            )
        else:
            self.sendPositiveResponse(tag, 'CLOSE completed')
            self.mbox.removeListener(self)
            self.mbox = None
            self.state = 'auth'

    def __cbClose(self, result, tag):
        self.sendPositiveResponse(tag, 'CLOSE completed')
        self.mbox.removeListener(self)
        self.mbox = None
        self.state = 'auth'

    def __ebClose(self, failure, tag):
        self.sendBadResponse(tag, 'CLOSE failed: ' + str(failure.value))

    def select_EXPUNGE(self, tag, args):
        if self.mbox.isWriteable():
            maybeDeferred(self.mbox.expunge).addCallbacks(
                self.__cbExpunge, self.__ebExpunge, (tag,), None, (tag,), None
            )
        else:
            self.sendPositiveResponse(tag, 'CLOSE completed')
            self.mbox.removeListener(self)
            self.mbox = None
            self.state = 'auth'

    def __cbExpunge(self, result, tag):
        for e in result:
            self.sendUntaggedResponse('%d EXPUNGE' % e)
        self.sendPositiveResponse(tag, 'EXPUNGE completed')
        self.mbox.removeListener(self)
        self.mbox = None
        self.state = 'auth'

    def __ebExpunge(self, failure, tag):
        self.sendBadResponse(tag, 'EXPUNGE failed: ' + str(failure.value))
        log.err(failure)

    def select_SEARCH(self, tag, args, uid=0):
        query = parseNestedParens(args)
        maybeDeferred(self.mbox.search, query, uid=uid).addCallbacks(
            self.__cbSearch, self.__ebSearch,
            (tag,), None, (tag,), None
        )

    def __cbSearch(self, result, tag):
        ids = ' '.join([str(i) for i in result])
        self.sendUntaggedResponse('SEARCH ' + ids)
        self.sendPositiveResponse(tag, 'SEARCH completed')

    def __ebSearch(self, failure, tag):
        self.sendBadResponse(tag, 'SEARCH failed: ' + str(failure.value))
        log.err(failure)

    def select_FETCH(self, tag, args, uid=0):
        parts = args.split(None, 1)
        if len(parts) != 2:
            raise IllegalClientResponse, args
        messages, args = parts
        messages = parseIdList(messages)
        query = parseNestedParens(args)
        while len(query) == 1 and isinstance(query[0], types.ListType):
            query = query[0]
        maybeDeferred(self.mbox.fetch, messages, query, uid=uid).addCallbacks(
            self.__cbFetch, self.__ebFetch,
            (tag,), None, (tag,), None
        )

    def __cbFetch(self, results, tag):
        for (mId, parts) in results.items():
            P = []
            map(P.extend, parts.items())
            self.sendUntaggedResponse(
                '%d FETCH %s' % (mId, collapseNestedLists([P]))
            )
        self.sendPositiveResponse(tag, 'FETCH completed')

    def __ebFetch(self, failure, tag):
        self.sendBadResponse(tag, 'FETCH failed: ' + str(failure.value))

    def select_STORE(self, tag, args, uid=0):
        parts = parseNestedParens(args)
        if 2 <= len(parts) <= 3:
            messages = parseIdList(parts[0])
            mode = parts[1].upper()
            if len(parts) == 3:
                flags = parts[2]
            else:
                flags = ()
        else:
            raise IllegalClientResponse, ('Wrong number of arguments', args)

        silent = mode.endswith('SILENT')
        if mode.startswith('+'):
            mode = 1
        elif mode.startswith('-'):
            mode = -1
        else:
            mode = 0

        maybeDeferred(self.mbox.store, messages, flags, mode, uid=uid).addCallbacks(
            self.__cbStore, self.__ebStore, (tag, silent), None, (tag,), None
        )

    def __cbStore(self, result, tag, silent):
        if result and not silent:
              for (k, v) in result.items():
                self.sendUntaggedResponse('%d FETCH FLAGS (%s)' % (k, ' '.join(v)))
        self.sendPositiveResponse(tag, 'STORE completed')

    def __ebStore(self, failure, tag):
        self.sendBadResponse(tag, 'Server error: ' + str(failure.value))

    def select_COPY(self, tag, args, uid=0):
        parts = splitQuoted(args)
        if len(parts) != 2:
            raise IllegalClientResponse, args
        ids = parts[0]
        mbox = self._parseMbox(parts[1])
        messages = parseIdList(ids)
        mbox = self.account.select(mbox)
        if not mbox:
            self.sendNegativeResponse(tag, 'No such mailbox: ' + parts[1])
        else:
            maybeDeferred(
                self.mbox.fetch, messages,
                ['BODY', [], 'INTERNALDATE', 'FLAGS'],
                uid=uid
            ).addCallbacks(
                self.__cbCopy, self.__ebCopy, (tag, mbox), None, (tag, mbox), None
            )

    def __cbCopy(self, messages, tag, mbox):
        # XXX - This should handle failures with a rollback or something
        addedDeferreds = []
        addedIDs = []
        failures = []
        for (id, msg) in messages.items():
            body = msg['BODY']
            flags = msg['FLAGS']
            date = msg['INTERNALDATE']
            try:
                d = mbox.addMessage(body, flags, date)
            except Exception, e:
                failures.append(e)
            else:
                if isinstance(d, defer.Deferred):
                    addedDeferreds.append(d)
                else:
                    addedIDs.append(d)
        d = defer.DeferredList(addedDeferreds)
        d.addCallback(self.__cbCopied, addedIDs, failures, tag, mbox)

    def __cbCopied(self, deferredIds, ids, failures, tag, mbox):
        for (result, status) in deferredIds:
            if status:
                ids.append(result)
            else:
                failures.append(result.value)
        if failures:
            self.sendNegativeResponse(tag, '[ALERT] Some messages were not copied')
        else:
            self.sendPositiveResponse(tag, 'COPY completed')

    def select_UID(self, tag, args):
        parts = args.split(None, 1)
        if len(parts) != 2:
            raise IllegalClientResponse, args

        command = parts[0].upper()
        args = parts[1]

        if command not in ('COPY', 'FETCH', 'STORE', 'SEARCH'):
            raise IllegalClientResponse, args

        f = getattr(self, 'select_' + command)
        f(tag, args, uid=1)

    #
    # IMailboxListener implementation
    # 
    def modeChanged(self, writeable):
        if writeable:
            self.sendPositiveResponse(message='[READ-WRITE]')
        else:
            self.sendPositiveResponse(message='[READ-ONLY]')

    def flagsChanged(self, newFlags):
        for (mId, flags) in newFlags.items():
            self.sendUntaggedResponse('%d FETCH (FLAGS (%s))' % (mId, ' '.join(flags)))

    def newMessages(self, exists, recent):
        if exists is not None:
            self.sendUntaggedResponse('%d EXISTS' % exists)
        if recent is not None:
            self.sendUntaggedResponse('%d RECENT' % recent)

class UnhandledResponse(IMAP4Exception): pass

class NegativeResponse(IMAP4Exception): pass

class NoSupportedAuthentication(IMAP4Exception):
    def __init__(self, serverSupports, clientSupports):
        IMAP4Exception.__init__(self, 'No supported authentication schemes available')
        self.serverSupports = serverSupports
        self.clientSupports = clientSupports

class IllegalServerResponse(IMAP4Exception): pass

class IMAP4Client(basic.LineReceiver):
    """IMAP4 client protocol implementation
    
    @ivar state: A string representing the state the connection is currently
    in.
    """
    __implements__ = (IMailboxListener,)

    tags = None
    waiting = None
    queued = None
    tagID = 1
    state = None
    
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

    def lineReceived(self, line):
        # print 'C: ' + line
        if self._parts is None:
            lastPart = line.rfind(' ')
            if lastPart != -1:
                lastPart = line[lastPart + 1:]
                if lastPart.startswith('{') and lastPart.endswith('}'):
                    # It's a literal a-comin' in
                    try:
                        octets = int(lastPart[1:-1])
                    except ValueError:
                        raise IllegalServerResponse(line)
                    self._tag, parts = line.split(None, 1)
                    self._setupForLiteral(parts, octets)
                    return
                else:
                    # It isn't a literal at all
                    self._regularDispatch(line)
            else:
                self._regularDispatch(line)
        else:
            # If an expression is in progress, no tag is required here
            # Since we didn't find a literal indicator, this expression
            # is done.
            self._parts.append(line)
            tag, rest = self._tag, ''.join(self._parts)
            self._tag = self._parts = None
            self.dispatchCommand(tag, rest)

    def _regularDispatch(self, line):
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise IllegalServerResponse, line
        tag, rest = parts
        self.dispatchCommand(tag, rest)

    def _setupForLiteral(self, rest, octets):
        self._pendingBuffer = self.messageFile(octets)
        self._pendingSize = octets
        self._parts = [rest, '\r\n']
        self.setRawMode()

    def messageFile(self, octets):
        """Create a file to which an incoming message may be written.
        
        @type octets: C{int}
        @param octets: The number of octets which will be written to the file
        
        @rtype: Any object which implements C{write(string)} and
        C{seek(int, int)}
        @return: A file-like object
        """
        if octets > self._memoryFileLimit:
            return tempfile.TemproraryFile()
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
        else:
            self._defaultHandler(tag, rest)

    def response_AUTH(self, tag, rest):
        self._defaultHandler(tag, rest)

    def _defaultHandler(self, tag, rest):
        if tag == '*' or tag == '+':
            if not self.waiting:
                self._extraInfo([rest])
            else:
                cmd = self.tags[self.waiting]
                if tag == '+':
                    cmd.continuation.callback(rest)
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
            self.sendLine(' '.join((t, cmd.command, cmd.args)))
            self.waiting = t
    
    def _extraInfo(self, lines):
        # XXX - This is terrible.
        # XXX - Also, this should collapse temporally proximate calls into single
        #       invocations of IMailboxListener methods, where possible.
        flags = {}
        for L in lines:
            if L.find('EXISTS') != -1:
                self.newMessages(int(L.split()[0]), None)
            elif L.find('RECENT') != -1:
                self.newMessages(None, int(L.split()[0]))
            elif L.find('READ-ONLY') != -1:
                self.modeChanged(0)
            elif L.find('READ-WRITE') != -1:
                self.modeChanged(1)
            elif L.find('FETCH') != -1:
                for (mId, fetched) in self.__cbFetch(([L], None)).items():
                    sum = []
                    for f in fetched.get('FLAGS', []):
                        sum.append(f)
                    flags.setdefault(mId, []).extend(sum)
            else:
                log.msg('Unhandled unsolicited response: ' + repr(L))
        if flags:
            self.flagsChanged(flags)

    def sendCommand(self, cmd):
        cmd.defer = defer.Deferred()
        if self.waiting:
            self.queued.append(cmd)
            return cmd.defer
        t = self.makeTag()
        self.tags[t] = cmd
        self.sendLine(' '.join((t, cmd.command, cmd.args)))
        self.waiting = t
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
        args = ''
        resp = ('CAPABILITY',)
        d = self.sendCommand(Command(cmd, args, wantResponse=resp))
        d.addCallback(self.__cbCapabilities)
        return d

    def __cbCapabilities(self, (lines, tagline)):
        caps = {}
        for rest in lines:
            rest = rest.split()[1:]
            for cap in rest:
                eq = cap.find('=')
                if eq == -1:
                    caps[cap] = None
                else:
                    caps.setdefault(cap[:eq], []).append(cap[eq+1:])
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


    def authenticate(self, secret):
        """Attempt to enter the authenticated state with the server

        This command is allowed in the Non-Authenticated state.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the authentication
        succeeds and whose errback will be invoked otherwise.
        """
        def getAuthMethods(caps):
            return caps.get('AUTH', [])
        if self._capCache is None:
            d = self.getCapabilities()
        else:
            d = defer.succeed(self._capCache)
        d.addCallback(getAuthMethods).addCallback(self.__cbAuthenticate, secret)
        return d

    def __cbAuthenticate(self, auths, secret):
        for scheme in auths:
            if scheme.upper() in self.authenticators:
                break
        else:
            raise NoSupportedAuthentication(auths, self.authenticators.keys())

        continuation = defer.Deferred()
        continuation.addCallback(self.__cbContinueAuth, scheme, secret)
        d = self.sendCommand(Command('AUTHENTICATE', scheme, continuation))
        d.addCallback(self.__cbAuth)
        return d

    def __cbContinueAuth(self, rest, scheme, secret):
        try:
            chal = base64.decodestring(rest + '\n')
        except binascii.Error:
            # XXX - Uh
            self.transport.loseConnection()
        else:
            auth = self.authenticators[scheme]
            chal = auth.challengeResponse(secret, chal)
            self.sendLine(base64.encodestring(chal))

    def __cbAuth(self, *args, **kw):
        return None

    def login(self, username, password):
        """Authenticate with the server using a username and password

        This command is allowed in the Non-Authenticated state.  If the
        server supports the STARTTLS capability and our transport support
        TLS, TLS is negotiated before the login command is issued.

        @type username: C{str}
        @param username: The username to log in with

        @type password: C{str}
        @param password: The password to log in with

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if login is successful
        and whose errback is invoked otherwise.
        """
        d = maybeDeferred(self.getCapabilities)
        d.addCallbacks(
            self.__cbLoginCaps,
            self.__ebLoginCaps,
            callbackArgs=(username, password),
        )
        return d

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
        tryTLS = 'STARTTLS' in capabilities and implements(self.transport, ITLSTransport)
        if tryTLS:
            ctx = self._getContextFactory()
            if ctx:
                d = self.sendCommand(Command('STARTTLS'))
                d.addCallbacks(
                    self.__cbLoginTLS,
                    self.__ebLoginTLS,
                    callbackArgs=(username, password, ctx),
                )
                return d
            else:
                log.err("Server wants us to use TLS, but we don't have "
                        "a Context Factory!")
        else:
            log.msg("Server has no TLS support. logging in over cleartext!")
            args = ' '.join((username, password))
            return self.sendCommand(Command('LOGIN', args))

    def __ebLoginCaps(self, failure):
        log.err(failure)
        return failure
    
    def __cbLoginTLS(self, result, username, password, context):
        self.transport.startTLS(context)
        self.context = context
        # Flush capability cache now!
        self._capCache = None
        args = ' '.join((username, password))
        return self.sendCommand(Command('LOGIN', args))
        
    def __ebLoginTLS(self, failure):
        log.err(failure)
        return failure

    def select(self, mailbox):
        """Select a mailbox

        This command is allowed in the Authenticated and Selected states.

        @type mailbox: C{str}
        @param mailbox: The name of the mailbox to select

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with mailbox
        information if the select is successful and whose errback is
        invoked otherwise.
        """
        cmd = 'SELECT'
        args = mailbox.encode('imap4-utf-7')
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
        is invoked otherwise.
        """
        cmd = 'EXAMINE'
        args = mailbox.encode('imap4-utf-7')
        resp = ('FLAGS', 'EXISTS', 'RECENT', 'UNSEEN', 'PERMANENTFLAGS', 'UIDVALIDITY')
        d = self.sendCommand(Command(cmd, args, wantResponse=resp))
        d.addCallback(self.__cbSelect, 0)
        return d

    def __cbSelect(self, (lines, tagline), rw):
        # In the absense of specification, we are free to assume:
        #   READ-WRITE access
        datum = {'READ-WRITE': rw}
        lines.append(tagline)
        for parts in lines:
            split = parts.split()
            if len(split) == 2:
                if split[1].upper().strip() == 'EXISTS':
                    try:
                        datum['EXISTS'] = int(split[0])
                    except ValueError:
                        raise IllegalServerResponse(parts)
                elif split[1].upper().strip() == 'RECENT':
                    try:
                        datum['RECENT'] = int(split[0])
                    except ValueError:
                        raise IllegalServerResponse(parts)
                else:
                    log.err('Unhandled SELECT response (1): ' + parts)
            elif split[0].upper().strip() == 'FLAGS':
                split = parts.split(None, 1)
                datum['FLAGS'] = tuple(parseNestedParens(split[1])[0])
            elif split[0].upper().strip() == 'OK':
                begin = parts.find('[')
                end = parts.find(']')
                if begin == -1 or end == -1:
                    raise IllegalServerResponse(parts)
                else:
                    content = parts[begin+1:end].split(None, 1)
                    if len(content) >= 1:
                        key = content[0].upper()
                        if key == 'READ-ONLY':
                            datum['READ-WRITE'] = 0
                        elif key == 'READ-WRITE':
                            datum['READ-WRITE'] = 1
                        elif key == 'UIDVALIDITY':
                            try:
                                datum['UIDVALIDITY'] = int(content[1])
                            except ValueError:
                                raise IllegalServerResponse(parts)
                        elif key == 'UNSEEN':
                            try:
                                datum['UNSEEN'] = int(content[1])
                            except ValueError:
                                raise IllegalServerResponse(parts)
                        elif key == 'PERMANENTFLAGS':
                            datum['PERMANENTFLAGS'] = tuple(parseNestedParens(content[1])[0])
                        else:
                            log.err('Unhandled SELECT response (2): ' + parts)
                    else:
                        log.err('Unhandled SELECT response (3): ' + parts)
            else:
                log.err('Unhandled SELECT response (4): ' + parts)
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
        return self.sendCommand(Command('CREATE', name.encode('imap4-utf-7')))

    def delete(self, name):
        """Delete a mailbox

        This command is allowed in the Authenticated and Selected states.

        @type name: C{str}
        @param name: The name of the mailbox to delete.

        @rtype: C{Deferred}
        @return: A deferred whose calblack is invoked if the mailbox is
        deleted successfully and whose errback is invoked otherwise.
        """
        return self.sendCommand(Command('DELETE', name.encode('imap4-utf-7')))

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
        oldname = oldname.encode('imap4-utf-7')
        newname = newname.encode('imap4-utf-7')
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
        return self.sendCommand(Command('SUBSCRIBE', name.encode('imap4-utf-7')))

    def unsubscribe(self, name):
        """Remove a mailbox from the subscription list

        This command is allowed in the Authenticated and Selected states.

        @type name: C{str}
        @param name: The mailbox to unsubscribe

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the unsubscription
        is successful and whose errback is invoked otherwise.
        """
        return self.sendCommand(Command('UNSUBSCRIBE', name.encode('imap4-utf-7')))

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
        for L in lines:
            parts = parseNestedParens(L)
            if len(parts) != 4:
                raise IllegalServerResponse, L
            if parts[0] == command:
                parts[1] = tuple(parts[1])
                results.append(tuple(parts[1:]))
        return results

    def status(self, mailbox, *names):
        """Retrieve the status of the given mailbox

        This command is allowed in the Authenticated and Selected states.

        @type mailbox: C{str}
        @param mailbox: The name of the mailbox to query

        @type names: C{str}
        @param names: The status names to query.  These may be any number of:
        MESSAGES, RECENT, UIDNEXT, UIDVALIDITY, and UNSEEN.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with the status information
        if the command is successful and whose errback is invoked otherwise.
        """
        cmd = 'STATUS'
        args = "%s (%s)" % (mailbox.encode('imap4-utf-7'), ' '.join(names))
        resp = ('STATUS',)
        d = self.sendCommand(Command(cmd, args, resp))
        d.addCallback(self.__cbStatus)
        return d

    def __cbStatus(self, (lines, last)):
        status = {}
        for line in lines:
            parts = parseNestedParens(line)
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
        """Add the given message to the currently selected mailbox

        This command is allowed in the Authenticated and Selected states.

        @type mailbox: C{str}
        @param mailbox: The mailbox to which to add this message.

        @type message: Any file-like object
        @param message: The message to add, in RFC822 format.

        @type flags: Any iterable of C{str}
        @param flags: The flags to associated with this message.

        @type date: C{str}
        @param date: The date to associate with this message.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when this command
        succeeds or whose errback is invoked if it fails.
        """
        message.seek(0, 2)
        L = message.tell()
        message.seek(0, 0)
        fmt = '%s (%s)%s%s {%d}'
        if date:
            date = '"%s"' % date
        cmd = fmt % (
            mailbox.encode('imap4-utf-7'), ' '.join(flags),
            date and ' ' or '', date, L
        )
        continuation = defer.Deferred()
        continuation.addCallback(self.__cbContinueAppend, message)
        continuation.addErrback(self.__ebContinueAppend)
        d = self.sendCommand(Command('APPEND', cmd, continuation))
        d.addCallback(self.__cbAppend)
        return d

    def __cbContinueAppend(self, lines, message):
        s = basic.FileSender()
        return s.beginFileTransfer(message, self.transport, lambda x: x)

    def __ebContinueAppend(self, failure):
        log.err()
        return failure

    def __cbAppend(self, result):
        return None

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
        for line in lines:
            parts = line.split(None, 1)
            if len(parts) == 2:
                if parts[1] == 'EXPUNGE':
                    try:
                        ids.append(int(parts[0]))
                    except ValueError:
                        raise IllegalServerResponse, line
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
        for line in lines:
            parts = line.split(None, 1)
            if len(parts) == 2:
                if parts[0] == 'SEARCH':
                    try:
                        ids.extend(map(int, parts[1].split()))
                    except ValueError:
                        raise IllegalServerResponse, line
        return ids

    def fetchUID(self, messages):
        """Retrieve the unique identifier for one or more messages

        This command is allowed in the Selected state.

        @type messages: C{str}
        @param messages: A message sequence set

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message sequence numbers to unique message identifiers, or whose
        errback is invoked if there is an error.
        """
        d = self._fetch(messages, useUID=0, uid=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchFlags(self, messages, uid=0):
        """Retrieve the flags for one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet}
        @param messages: The messages for which to retrieve flags.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to lists of flags, or whose errback is invoked if
        there is an error.
        """
        d = self._fetch(str(messages), useUID=uid, flags=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchInternalDate(self, messages, uid=0):
        """Retrieve the internal date associated with one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet}
        @param messages: The messages for which to retrieve the internal date.

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to date strings, or whose errback is invoked
        if there is an error.  Date strings take the format of 
        \"<day-month-year time timezone\".
        """
        d = self._fetch(str(messages), useUID=uid, internaldate=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchEnvelope(self, messages, uid=0):
        """Retrieve the envelope data for one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet}
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
        d = self._fetch(str(messages), useUID=uid, envelope=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchBodyStructure(self, messages, uid=0):
        """Retrieve the structure of the body of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{MessageSet}
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
        d = self._fetch(messages, useUID=uid, bodystructure=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchSimplifiedBody(self, messages, uid=0):
        """Retrieve the simplified body structure of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{str}
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
        d = self._fetch(messages, useUID=uid, body=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchMessage(self, messages, uid=0):
        """Retrieve one or more entire messages

        This command is allowed in the Selected state.

        @type messages: C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to message objects, or whose errback is invoked
        if there is an error.
        """
        d = self._fetch(messages, useUID=uid, rfc822=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchHeaders(self, messages, uid=0):
        """Retrieve headers of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dicts of message headers, or whose errback is
        invoked if there is an error.
        """
        d = self._fetch(messages, useUID=uid, rfc822header=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchBody(self, messages, uid=0):
        """Retrieve body text of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to file-like objects containing body text, or whose
        errback is invoked if there is an error.
        """
        d = self._fetch(messages, useUID=uid, rfc822text=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchSize(self, messages, uid=0):
        """Retrieve the size, in octets, of one or more messages

        This command is allowed in the Selected state.

        @type messages: C{str}
        @param messages: A message sequence set

        @type uid: C{bool}
        @param uid: Indicates whether the message sequence set is of message
        numbers or of unique message IDs.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to sizes, or whose errback is invoked if there is
        an error.
        """
        d = self._fetch(messages, useUID=uid, rfc822size=1)
        d.addCallback(self.__cbFetch)
        return d

    def fetchFull(self, messages, uid=0):
        """Retrieve several different fields of one or more messages

        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate},
        C{fetchSize}, C{fetchEnvelope}, and C{fetchSimplifiedBody}
        functions.

        @type messages: C{str}
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
        d = self._fetch(
            messages, useUID=uid, flags=1, internaldate=1,
            rfc822size=1, envelope=1, body=1
        )
        d.addCallback(self.__cbFetch)
        return d

    def fetchAll(self, messages, uid=0):
        """Retrieve several different fields of one or more messages

        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate},
        C{fetchSize}, and C{fetchEnvelope} functions.

        @type messages: C{str}
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
        d = self._fetch(
            messages, useUID=uid, flags=1, internaldate=1,
            rfc822size=1, envelope=1
        )
        d.addCallback(self.__cbFetch)
        return d

    def fetchFast(self, messages, uid=0):
        """Retrieve several different fields of one or more messages

        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate}, and
        C{fetchSize} functions.

        @type messages: C{str}
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
        d = self._fetch(
            messages, useUID=uid, flags=1, internaldate=1, rfc822size=1
        )
        d.addCallback(self.__cbFetch)
        return d

    def __cbFetch(self, (lines, last)):
        flags = {}
        for line in lines:
            parts = line.split(None, 2)
            if len(parts) == 3:
                if parts[1] == 'FETCH':
                    try:
                        id = int(parts[0])
                    except ValueError:
                        raise IllegalServerResponse, line
                    else:
                        data = parseNestedParens(parts[2])
                        while len(data) == 1 and isinstance(data, types.ListType):
                            data = data[0]
                        while data:
                            if len(data) < 2:
                                raise IllegalServerResponse, "Not enough arguments", data
                            flags.setdefault(id, {})[data[0]] = data[1]
                            del data[:2]
                else:
                    print '(2)Ignoring ', parts
            else:
                print '(3)Ignoring ', parts
        return flags

    def fetchSpecific(self, messages, uid=0, headerType=None,
                      headerNumber=None, headerArgs=None, peek=None,
                      offset=None, length=None):
        """Retrieve a specific section of one or more messages

        @type messages: C{str}
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
        elif isinstance(headerNumber, types.IntType):
            number = str(headerNumber)
        else:
            number = '.'.join(headerNumber)
        if headerType is None:
            header = ''
        elif number:
            header = '.' + headerType
        else:
            header = headerType
        if header:
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
        d.addCallback(self.__cbFetchSpecific)
        return d

    def __cbFetchSpecific(self, (lines, last)):
        info = {}
        for line in lines:
            parts = line.split(None, 2)
            if len(parts) == 3:
                if parts[1] == 'FETCH':
                    try:
                        id = int(parts[0])
                    except ValueError:
                        raise IllegalServerResponse, line
                    else:
                        info[id] = parseNestedParens(parts[2])
        return info

    def _fetch(self, messages, useUID=0, **terms):
        fetch = useUID and 'UID FETCH' or 'FETCH'
        cmd = '%s %s' % (messages, ' '.join([s.upper() for s in terms.keys()]))
        d = self.sendCommand(Command(fetch, cmd, wantResponse=('FETCH',)))
        return d

    def setFlags(self, messages, flags, silent=1, uid=0):
        """Set the flags for one or more messages.

        This command is allowed in the Selected state.

        @type messages: C{str}
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
        return self._store(messages, silent and 'FLAGS.SILENT' or 'FLAGS', flags, uid)

    def addFlags(self, messages, flags, silent=1, uid=0):
        """Add to the set flags for one or more messages.

        This command is allowed in the Selected state.

        @type messages: C{str}
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
        return self._store(messages, silent and '+FLAGS.SILENT' or '+FLAGS', flags, uid)

    def removeFlags(self, messages, flags, silent=1, uid=0):
        """Remove from the set flags for one or more messages.

        This command is allowed in the Selected state.

        @type messages: C{str}
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
        return self._store(messages, silent and '-FLAGS.SILENT' or '-FLAGS', flags, uid)

    def _store(self, messages, cmd, flags, uid):
        store = uid and 'UID STORE' or 'STORE'
        args = ' '.join((messages, cmd, '(%s)' % ' '.join(flags)))
        d = self.sendCommand(Command(store, args, wantResponse=('FETCH',)))
        d.addCallback(self.__cbFetch, lookFor='FLAGS')
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
        args = '%s %s' % (messages, mailbox.encode('imap4-utf-7'))
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

def parseIdList(s):
    res = MessageSet()
    parts = s.split(',')
    for p in parts:
        if ':' in p:
            low, high = p.split(':', 1)
            try:
                low = int(low)
                if high == '*':
                    res = res + (low, None)
                else:
                    res = res + (low, int(high))
            except ValueError:
                raise IllegalIdentifierError, p
        else:
            try:
                p = int(p)
            except ValueError:
                raise IllegalIdentifierError, p
            else:
                res = res + (p, p)
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

    Among the accepted keywords are:

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

def wildcardToRegexp(wildcard, delim):
    wildcard = wildcard.replace('*', '(?:.*?)')
    wildcard = wildcard.replace('%', '(?:(?:[^%s])*?)' % re.escape(delim))
    return re.compile(wildcard)

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
    inQuote = inWord = start = 0
    for (i, c) in zip(range(len(s)), s):
        if c == '"' and not inQuote:
            inQuote = 1
            start = i + 1
        elif c == '"' and inQuote:
            inQuote = 0
            result.append(s[start:i])
            start = i + 1
        elif not inWord and not inQuote and c not in ('"' + string.whitespace):
            inWord = 1
            start = i
        elif inWord and not inQuote and c in string.whitespace:
            if s[start:i] == 'NIL':
                result.append(None)
            else:
                result.append(s[start:i])
            start = i
            inWord = 0
    if inQuote:
        raise MismatchedQuoting(s)
    if inWord:
        if s[start:] == 'NIL':
            result.append(None)
        else:
            result.append(s[start:])
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

#    if reduce(operator.add, listsList, 0) == 0:
#        return splitQuoted(''.join(results))

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
                    contentStack[-1].append(s[i+1])
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

_ATOM_SPECIALS = '(){ %*"'
def _needsQuote(s):
    for c in s:
        if c < '\x20' or c > '\x7f':
            return 1
        if c in _ATOM_SPECIALS:
            return 1
    return 0

def _needsLiteral(s):
    # Change this to "return 1" to wig out stupid clients
    return '\n' in s or '\r' in s or len(s) > 1000

def collapseNestedLists(items):
    """Turn a nested list structure into an s-exp-like string.

    Strings in C{items} will be sent as literals if they contain CR or LF,
    quoted if they contain other whitespace, or sent unquoted otherwise.
    References to None in C{items} will be translated to the atom NIL.

    @type items: Any iterable

    @rtype: C{str}
    """
    pieces = []
    for i in items:
        if i is None:
            pieces.extend([' ', 'NIL'])
        elif isinstance(i, types.StringTypes):
            if _needsLiteral(i):
                pieces.extend([' ', '{', str(len(i)), '}', IMAP4Server.delimiter, i])
            elif (not i.startswith('BODY')) and _needsQuote(i):
                pieces.extend([' ', _quote(i)])
            else:
                pieces.extend([' ', i])
        elif pieces and pieces[-1].upper() == 'BODY.PEEK':
            pieces.append('[%s]' % (collapseNestedLists(i),))
        else:
            pieces.extend([' ', '(%s)' % (collapseNestedLists(i),)])
    return ''.join(pieces[1:])

class IClientAuthentication(components.Interface):
    def getName(self):
        """Return an identifier associated with this authentication scheme.
        
        @rtype: C{str}
        """

    def challengeResponse(self, secret, challenge):
        """Generate a challenge response string"""

class CramMD5ClientAuthenticator:
    __implements__ = (IClientAuthentication,)

    def __init__(self, user):
        self.user = user

    def getName(self):
        return "CRAM-MD5"

    def challengeResponse(self, secret, chal):
        response = util.keyed_md5(secret, chal)
        return '%s %s' % (self.user, response)

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

class IAccount(components.Interface):
    """Interface for Account classes
    
    Implementors of this interface must also subclass
    C{twisted.cred.perspective.Perspective}
    """

    def addMailbox(self, name, mbox = None):
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
    
    def create(self, pathspec):
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
    
    def select(self, name, rw=1):
        """Acquire a mailbox, given its name.
        
        @type name: C{str}
        @param name: The mailbox to acquire
        
        @type rw: C{bool}
        @param rw: If a true value, request a read-write version of this
        mailbox.  If a false value, request a read-only version.
        
        @rtype: Any object implementing C{IMailbox} or C{Deferred}
        @return: The mailbox object, or a C{Deferred} whose callback will
        be invoked with the mailbox object.
        """
    
    def delete(self, name):
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
    
    def rename(self, oldname, newname):
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
    
    def isSubscribed(self, name):
        """Check the subscription status of a mailbox
        
        @type name: C{str}
        @param name: The name of the mailbox to check
        
        @rtype: C{Deferred} or C{bool}
        @return: A true value if the given mailbox is currently subscribed
        to, a false value otherwise.  A C{Deferred} may also be returned
        whose callback will be invoked with one of these values.  """
    
    def subscribe(self, name):
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
    
    def unsubscribe(self, name):
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
    
    def listMailboxes(self, ref, wildcard):
        """List all the mailboxes that meet a certain criteria
        
        @type ref: C{str}
        @param ref: The context in which to apply the wildcard
        
        @type wildcard: C{str}
        @param wildcard: An expression against which to match mailbox names.
        '*' matches any number of characters in a mailbox name, and '%'
        matches similarly, but will not match across hierarchical boundaries.
        
        @rtype: C{list} of C{tuple}
        @return: A list of C{(mailboxName, mailboxObject)} which meet the
        given criteria.
        """
    
class MemoryAccount(perspective.Perspective):
    __implements__ = (perspective.Perspective.__implements__, IAccount)

    mailboxes = None
    subscriptions = None
    top_id = 0
    
    def __init__(self, name):
        perspective.Perspective.__init__(self, name, name)
        self.mailboxes = {}
        self.subscriptions = []

    def allocateID(self):
        id = self.top_id
        self.top_id += 1
        return id

    def addMailbox(self, name, mbox = None):
        name = name.upper()
        if self.mailboxes.has_key(name):
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
                raise

    def _emptyMailbox(self, name, id):
        raise NotImplementedError

    def select(self, name, readwrite=1):
        return self.mailboxes.get(name.upper())

    def delete(self, name):
        name = name.upper()
        # See if this mailbox exists at all
        mbox = self.mailboxes.get(name)
        if not mbox:
            raise MailboxException, "No such mailbox"
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
        if not self.mailboxes.has_key(oldname):
            raise NoSuchMailbox, oldname

        inferiors = self._inferiorNames(oldname)
        inferiors = [(o, o.replace(oldname, newname, 1)) for o in inferiors]

        for (old, new) in inferiors:
            if self.mailboxes.has_key(new):
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
    

class IMailbox(components.Interface):
    def getUIDValidity(self):
        """Return the unique validity identifier for this mailbox.

        @rtype: C{int}
        """

    def getUIDNext(self):
        """Return the likely UID for the next message added to this mailbox.
        
        @rtype: C{int}
        """
    
    def getFlags(self):
        """Return the flags defined in this mailbox

        Flags with the \\ prefix are reserved for use as system flags.

        @rtype: C{list} of C{str}
        @return: A list of the flags that can be set on messages in this mailbox.
        """

    def getMessageCount(self):
        """Return the number of messages in this mailbox.
        
        @rtype: C{int}
        """

    def getRecentCount(self):
        """Return the number of messages with the 'Recent' flag.
        
        @rtype: C{int}
        """

    def getUnseenCount(self):
        """Return the number of messages with the 'Unseen' flag.
        
        @rtype: C{int}
        """

    def isWriteable(self):
        """Get the read/write status of the mailbox.

        @rtype: C{int}
        @return: A true value if write permission is allowed, a false value otherwise.
        """

    def destroy(self):
        """Called before this mailbox is deleted, permanently.

        If necessary, all resources held by this mailbox should be cleaned
        up here.  This function _must_ set the \\Noselect flag on this
        mailbox.
        """

    def getHierarchicalDelimiter(self):
        """Get the character which delimits namespaces for in this mailbox.

        @rtype: C{str}
        """

    def requestStatus(self, names):
        """Return status information about this mailbox.

        @type names: Any iterable
        @param names: The status names to return information regarding

        @rtype: C{dict} or C{Deferred}
        @return: A dictionary containing status information about the
        requested names is returned.  If the process of looking this
        information up would be costly, a deferred whose callback will
        eventually be passed this dictionary is returned instead.
        """

    def addListener(self, listener):
        """Add a mailbox change listener
        
        @type listener: Any object which implements C{IMailboxListener}
        @param listener: An object to add to the set of those which will
        be notified when the contents of this mailbox change.
        """
    
    def removeListener(self, listener):
        """Remove a mailbox change listener
        
        @type listener: Any object previously added to and not removed from
        this mailbox as a listener.
        @param listener: The object to remove from the set of listeners.
        
        @raise ValueError: Raised when the given object is not a listener for
        this mailbox.
        """

    def addMessage(self, message, flags = (), date = None):
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

    def expunge(self):
        """Remove all messages flagged \\Deleted.

        @rtype: C{list} or C{Deferred}
        @return: The list of message sequence numbers which were deleted,
        or a C{Deferred} whose callback will be invoked with such a list.

        @raise ReadOnlyMailbox: Raised if this Mailbox is not open for
        read-write.
        """

    def search(self, query, uid):
        """Search for messages that meet the given query criteria.

        @type query: C{list}
        @param query: The search criteria

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs;
        otherwise they are message sequence IDs.

        @rtype: C{list} or C{Deferred}
        @return: A list of message sequence numbers or message UIDs which
        match the search criteria or a C{Deferred} whose callback will be
        invoked with such a list.
        """

    def fetch(self, messages, parts, uid):
        """Retrieve one or more portions of one or more messages.

        @type messages: iterable of C{int}
        @param messages: The identifiers of messages to retrieve information
        about

        @type parts: C{list}
        @param parts: The message portions to retrieve.

        @type uid: C{bool}
        @param uid: If true, the IDs specified in the query are UIDs;
        otherwise they are message sequence IDs.

        @rtype: C{dict} or C{Deferred}
        @return: A C{dict} mapping message identifiers to C{dicts} mapping
        portion identifiers to strings representing that portion of that message, or a
        C{Deferred} whose callback will be invoked with such a C{dict}.
        """

    def store(self, messages, flags, mode, uid):
        """Set the flags of one or more messages.

        @type messages: sequence of C{int}
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
        @return: A C{dict} mapping message identifiers to sequences of C{str}
        representing the flags set on the message after this operation has
        been performed, or a C{Deferred} whose callback will be invoked with
        such a C{dict}.

        @raise ReadOnlyMailbox: Raised if this mailbox is not open for
        read-write.
        """

import codecs
def modified_base64(s):
    # XXX - 2.1, grr
    # return binascii.b2a_base64(s)[:-1].rstrip('=').replace('/', ',')
    s = binascii.b2a_base64(s)[:-1]
    while s[-1] == '=':
        s = s[:-1]
    return s.replace('/', ',')

def modified_unbase64(s):
    return binascii.a2b_base64(s.replace(',', '/') + '===')

def encoder(s):
    r = []
    _in = []
    for c in s:
        if ord(c) in (range(0x20, 0x25) + range(0x27, 0x7e)):
            if _in:
                r.extend(['&', modified_base64(''.join(_in)), '-'])
                del _in[:]
            r.append(c)
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

def decoder(s):
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
    def decode(self, s, errors='strict'):
        return encoder(s)

def imap4_utf_7(name):
    if name == 'imap4-utf-7':
        return (encoder, decoder, StreamReader, StreamWriter)
codecs.register(imap4_utf_7)

__all__ = [
    'IMAP4Server', 'IMAP4Client', 'IMAP4Exception', 'IllegalClientResponse',
    'IllegalOperation', 'IllegalMailboxEncoding', 'IMailboxListener',
    'UnhandledResponse', 'NegativeResponse', 'NoSupportedAuthentication',
    'IllegalServerResponse', 'IllegalIdentifierError', 'IllegalQueryError',
    'MismatchedNesting', 'MismatchedQuoting', 'IClientAuthentication',
    'CramMD5ClientAuthenticator', 'MailboxException', 'MailboxCollision',
    'NoSuchMailbox', 'ReadOnlyMailbox', 'IAccount', 'MemoryAccount',
    'IMailbox'
]
