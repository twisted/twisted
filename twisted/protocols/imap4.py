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

API Stability: Unstable

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

from __future__ import nested_scopes

from twisted.protocols import basic
from twisted.internet import defer
from twisted.python import log, components

import binascii, operator, re, string, types, rfc822

class IMAP4Exception(Exception):
    def __init__(self, *args):
        Exception.__init__(self, *args)

class IllegalClientResponse(IMAP4Exception): pass

class IMAP4Server(basic.LineReceiver):

    """
    Protocol implementation for an IMAP4rev1 server.
    
    The server can be in any of four states:
        Non-authenticated
        Authenticated
        Selected
        Logout
    """

    # Authentication schemes
    IMAP_AUTH = ()
    
    # Capabilities supported by this server
    CAPABILITIES = {}
    
    # Identifier for this server software
    IDENT = 'Twisted IMAP4rev1 Ready'
    
    # Mapping of tags to commands we have received
    tags = None
    
    # The account object for this connection
    account = None
    
    # The currently selected mailbox
    mbox = None
    
    # Command data to be processed when literal data is received
    _pendingLiteral = None
    _pendingBuffer = None
    _pendingSize = None
    
    def connectionMade(self):
        self.tags = {}
        self.state = 'unauth'
        self.sendServerGreeting()
    
    def rawDataReceived(self, data):
        self._pendingSize -= len(data)
        if self._pendingSize > 0:
            self._pendingBuffer.append(data)
        else:
            passon = ''
            if self._pendingSize < 0:
                data, passon = data[:self._pendingSize], data[self._pendingSize:]
            self._pendingBuffer.append(data)
            rest = ''.join(self._pendingBuffer)
            self._pendingBuffer = None
            self._pendingSize = None
            self._pendingLiteral.callback(rest)
            self._pendingLiteral = None
            if passon:
                self.setLineMode(passon)
    
    def lineReceived(self, line):
        # print 'S: ' + line
        args = line.split(None, 2)
        rest = None
        if len(args) == 3:
            tag, cmd, rest = args
        elif len(args) == 2:
            tag, cmd = args
        else:
            # XXX - This is rude.
            self.transport.loseConnection()
            raise IllegalClientResponse(line) 
    
        cmd = cmd.upper()
        self.dispatchCommand(tag, cmd, rest)

    def dispatchCommand(self, tag, cmd, rest):
        f = self.lookupCommand(cmd)
        if f:
            try:
                f(tag, rest)
            except Exception, e:
                self.sendBadResponse(tag, 'Server error: ' + str(e))
                log.deferr()
        else:
            self.sendBadResponse(tag, 'Unsupported command')

    def lookupCommand(self, cmd):
        return getattr(self, '_'.join((self.state, cmd.upper())), None)

    def sendServerGreeting(self):
        self.sendPositiveResponse(message=self.IDENT)
    
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
        self._pendingBuffer = []
        self._pendingSize = octets
        self._pendingLiteral = defer.Deferred()
        self.sendContinuationRequest('Ready for %d octets of text' % octets)
        self.setRawMode()
        return self._pendingLiteral

    def _respond(self, state, tag, message):
        if not tag:
            tag = '*'
        if not message:
            self.sendLine(' '.join((tag, state)))
        else:
            self.sendLine(' '.join((tag, state, message)))

    def unauth_CAPABILITY(self, tag, args):
        caps = 'IMAP4rev1'
        for c, v in self.CAPABILITIES.items():
            if v:
                caps = ' '.join([caps] + [('%s=%s' % (c, cap)) for cap in v])
            else:
                caps = ' '.join((caps, c))
        self.sendUntaggedResponse('CAPABILITY ' + caps)
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
    
    def unauth_NOOP(self, tag, args):
        self.sendPositiveResponse(tag, 'NOOP No operation performed')
    
    auth_NOOP = unauth_NOOP
    select_NOOP = unauth_NOOP
    logout_NOOP = unauth_NOOP
    
    def unauth_AUTHENTICATE(self, tag, args):
        args = args.upper().strip()
        if not self.authenticators.has_key(args):
            self.sendNegativeResponse(tag, 'AUTHENTICATE method unsupported')
        else:
            auth = self.authenticators[args]
            try:
               challenge = auth.generateChallenge()
            except Exception, e:
                self.sendBadResponse(tag, 'Server error: ' + str(e))
            else:
                coded = binascii.b2a_base64(challenge)[:-1]
                d = self.sendContinuationRequest(coded)
                d.addCallback(self._cbAuthChunk, challenge, tag)
    
    def _cbAuthChunk(self, result, challenge, tag):
        try:
            challenge = auth.generateChallenge(challenge, result)
        except AuthenticationError:
            self.sendNegativeResponse(tag, 'Authentication failed')
        else:
            if challenge == 1:
                self.sendPositiveResponse(tag, 'Authentication successful')
                self.state = 'auth'
            else:
                d = self.sendContinuationRequest(challenge)
                d.addCallback(self._cbAuthChunk, challenge, tag)

    def unauth_LOGIN(self, tag, args):
        args = args.split()
        if len(args) != 2:
            self.sendBadResponse(tag, 'Wrong number of arguments')
        else:
            d = self.authenticateLogin(*args)
            if isinstance(d, defer.Deferred):
                d.addCallbacks(self._cbLogin, self._ebLogin, callbackArgs=(tag,), errbackArgs=(tag,))
            else:
                self._cbLogin(d, tag)

    def authenticateLogin(self, user, passwd):
        """Lookup the account associated with the given parameters
        
        Override this method to define the desired authentication behavior.
        
        @type user: C{str}
        @param user: The username to lookup
        
        @type passwd: C{str}
        @param passwd: The password to login with
        
        @rtype: C{Account}
        @return: An appropriate account object, or None
        """
        return None
    
    def _cbLogin(self, account, tag):
        if account is None:
            self.sendNegativeResponse(tag, 'LOGIN failed')
        else:
            self.account = account
            self.sendPositiveResponse(tag, 'LOGIN succeeded')
            self.state = 'auth'
    
    def _ebLogin(self, failure, tag):
        self.sendBadResponse(tag, 'Server error: ' + str(failure.value))
    
    
    def auth_SELECT(self, tag, args):
        mbox = self.account.select(args)
        if mbox is None:
            self.sendNegativeResponse(tag, 'No such mailbox')
        else:
            self.state = 'select'
            
            flags = mbox.getFlags()
            self.sendUntaggedResponse(str(mbox.getMessageCount()) + ' EXISTS')
            self.sendUntaggedResponse(str(mbox.getRecentCount()) + ' RECENT')
            self.sendUntaggedResponse('FLAGS (%s)' % ' '.join(flags))
            self.sendPositiveResponse(None, '[UIDVALIDITY %d]' % mbox.getUID())

            if mbox.isWriteable():
                s = 'READ-WRITE'
            else:
                s = 'READ-ONLY'

            if self.mbox:
                self.account.release(mbox)
            self.mbox = mbox
            self.sendPositiveResponse(tag, '[%s] SELECT successful' % s)
    select_SELECT = auth_SELECT
    
    def auth_EXAMINE(self, tag, args):
        mbox = self.account.select(args, 0)
        if mbox is None:
            self.sendNegativeResponse(tag, 'No such mailbox')
        else:
            self.state = 'select'
            
            flags = mbox.getFlags()
            self.sendUntaggedResponse(str(mbox.getMessageCount()) + ' EXISTS')
            self.sendUntaggedResponse(str(mbox.getRecentCount()) + ' RECENT')
            self.sendUntaggedResponse('FLAGS (%s)' % ' '.join(flags))
            self.sendPositiveResponse(None, '[UIDVALIDITY %d]' % mbox.getUID())

            if self.mbox:
                self.account.release(mbox)
            self.mbox = mbox
            self.sendPositiveResponse(tag, '[READ-ONLY] EXAMINE successful')
    select_EXAMINE = auth_EXAMINE
    
    def auth_CREATE(self, tag, args):
        try:
            self.account.create(args.strip())
        except MailboxCollision, c:
            self.sendNegativeResponse(tag, str(c))
        else:
            self.sendPositiveResponse(tag, 'Mailbox created')
    select_CREATE = auth_CREATE
    
    def auth_DELETE(self, tag, args):
        try:
            self.account.delete(args.strip())
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Mailbox deleted')
    select_DELETE = auth_DELETE
    
    
    def auth_RENAME(self, tag, args):
        try:
            self.account.rename(*args.strip().split())
        except TypeError:
            self.sendBadResponse(tag, 'Invalid command syntax')
        except MailboxException, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Mailbox renamed')
    select_RENAME = auth_RENAME
    
    def auth_SUBSCRIBE(self, tag, args):
        try:
            self.account.subscribe(args.strip())
        except MailboxError, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Subscribed')
    select_SUBSCRIBE= auth_SUBSCRIBE
    
    def auth_UNSUBSCRIBE(self, tag, args):
        try:
            self.account.unsubscribe(args.strip())
        except MailboxError, m:
            self.sendNegativeResponse(tag, str(m))
        else:
            self.sendPositiveResponse(tag, 'Unsubscribed')
    select_UNSUBSCRIBE = auth_UNSUBSCRIBE

    def auth_LIST(self, tag, args):
        args = splitQuoted(args)
        if len(args) != 2:
            self.sendBadResponse(tag, 'Incorrect usage')
        else:
            ref, mbox = args
            mailboxes = self.account.listMailboxes(ref, mbox)
            for (name, box) in mailboxes:
                flags = '(%s)' % ' '.join(box.getFlags())
                delim = box.getHierarchicalDelimiter()
                self.sendUntaggedResponse('LIST %s "%s" %s' % (flags, delim, name))
            self.sendPositiveResponse(tag, 'LIST completed')
    select_UNSUBSCRIBE = auth_UNSUBSCRIBE

    def auth_LSUB(self, tag, args):
        args = splitQuoted(args)
        if len(args) != 2:
            self.sendBadResponse(tag, 'Incorrect usage')
        else:
            ref, mbox = args
            mailboxes = self.account.listMailboxes(ref, mbox)
            for (name, box) in mailboxes:
                if self.account.isSubscribed(name):
                    flags = '(%s)' % ' '.join(box.getFlags())
                    delim = box.getHierarchicalDelimiter()
                    self.sendUntaggedResponse('LSUB %s "%s" %s' % (flags, delim, name))
            self.sendPositiveResponse(tag, 'LSUB completed')
    select_LSUB = auth_LSUB

    def auth_STATUS(self, tag, args):
        names = parseNestedParens(args)
        if len(names) != 2:
            raise IllegalClientResponse(args)
        mailbox, names = names
        try:
            d = self.account.requestStatus(mailbox, names)
        except MailboxException, e:
            self.sendNegativeResponse(tag, str(e))
        else:
            if isinstance(d, defer.Deferred):
                d.addCallback(self._cbStatus, tag, mailbox)
                d.addErrback(self._ebStatus, tag, mailbox)
            else:
                self._cbStatus(d, tag)
    select_STATUS = auth_STATUS

    def _cbStatus(self, status, tag, box):
        line = ' '.join(['%s %s' % x for x in status.items()])
        self.sendUntaggedResponse('STATUS %s (%s)' % (box, line))
        self.sendPositiveResponse(tag, 'STATUS complete')
    
    def _ebStatus(self, failure, tag, box):
        self.sendBadResponse(tag, 'STATUS %s failed: %s' % (box, failure))
    
    def auth_APPEND(self, tag, args):
        parts = parseNestedParens(args)
        if len(parts) == 2:
            flags = ()
            date = rfc822.formatdate()
            size = parts[1]
        elif len(parts) == 3:
            if isinstance(parts[1], types.StringType):
                flags = ()
                date = parts[1]
            else:
                flags = parts[1]
                date = rfc822.formatdate()
            size = parts[2]
        elif len(parts) ==  4:
            flags = tuple(parts[1])
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
        d.addCallback(self._cbContinueAppend, tag, mbox, flags, date)
        d.addErrback(self._ebAppend, tag)
    select_APPEND = auth_APPEND

    def _cbContinueAppend(self, rest, tag, mbox, flags, date):
        d = mbox.addMessage(rest, flags, date)
        d.addCallback(self._cbAppend, tag, mbox)
        d.addErrback(self._ebAppend, tag)
    
    def _cbAppend(self, result, tag, mbox):
        self.sendUntaggedResponse('%d EXISTS' % mbox.getMessageCount())
        self.sendPositiveResponse(tag, 'APPEND complete')
    
    def _ebAppend(self, failure, tag):
        self.sendBadResponse(tag, 'APPEND failed: ' + str(failure))
    
    def select_CHECK(self, tag, args):
        d = self.checkpoint()
        if d is None:
            self._cbCheck(None, tag)
        else:
            d.addCallbacks(
                self._cbCheck,
                self._ebCheck,
                callbackArgs=(tag,),
                errbackArgs=(tag,)
            )

    def _cbCheck(self, result, tag):
        self.sendPositiveResponse(tag, 'CHECK completed')
    
    def _ebCheck(self, failure, tag):
        self.sendBadResponse(tag, 'CHECK failed: ' + str(failure))
    
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
            d = self.mbox.expunge()
            if isinstance(d, defer.Deferred):
                d.addCallbacks(
                    self._cbClose,
                    self._ebClose,
                    callbackArgs=(tag,),
                    errbackArgs=(tag,)
                )
            else:
                self._cbClose(d, tag)
        else:
            self.sendPositiveResponse(tag, 'CLOSE completed')
            self.account.release(self.mbox)
            self.mbox = None
            self.state = 'auth'

    def _cbClose(self, result, tag):
        self.sendPositiveResponse(tag, 'CLOSE completed')
        self.account.release(self.mbox)
        self.mbox = None
        self.state = 'auth'

    def _ebClose(self, failure, tag):
        self.sendBadResponse(tag, 'CLOSE failed: ' + str(failure))
    
    def select_EXPUNGE(self, tag, args):
        if self.mbox.isWriteable():
            d = self.mbox.expunge()
            if isinstance(d, defer.Deferred):
                d.addCallbacks(
                    self._cbExpunge,
                    self._ebExpunge,
                    callbackArgs=(tag,),
                    errbackArgs=(tag,)
                )
            else:
                self._cbExpunge(d, tag)
        else:
            self.sendPositiveResponse(tag, 'CLOSE completed')
            self.account.release(self.mbox)
            self.mbox = None
            self.state = 'auth'

    def _cbExpunge(self, result, tag):
        for e in result:
            self.sendUntaggedResponse('%d EXPUNGE' % e)
        self.sendPositiveResponse(tag, 'EXPUNGE completed')
        self.account.release(self.mbox)
        self.mbox = None
        self.state = 'auth'

    def _ebExpunge(self, failure, tag):
        self.sendBadResponse(tag, 'EXPUNGE failed: ' + str(failure))
    
    def select_SEARCH(self, tag, args):
        query = parseNestedParens(args)
        d = self.mbox.search(query)
        if isinstance(d, defer.Deferred):
            d.addCallbacks(
                self._cbSearch,
                self._ebSearch,
                callbackArgs=(tag,),
                errbackArgs=(tag,)
            )
        else:
            self._cbSearch(d, tag)


class UnhandledResponse(IMAP4Exception): pass

class NegativeResponse(IMAP4Exception): pass

class NoSupportedAuthentication(IMAP4Exception):
    def __init__(self, serverSupports, clientSupports):
        IMAP4Exception.__init__(self, 'No supported authentication schemes available')
        self.serverSupports = serverSupports
        self.clientSupports = clientSupports

class IllegalServerResponse(IMAP4Exception): pass

class IMAP4Client(basic.LineReceiver):
    tags = None
    waiting = None
    queued = None
    tagID = 1
    state = None
    
    # Capabilities are not allowed to change during the session
    # So cache the first response and use that for all later
    # lookups
    _capCache = None

    # Authentication is pluggable.  This maps names to IClientAuthentication
    # objects.
    authenticators = None

    STATUS_CODES = ('OK', 'NO', 'BAD', 'PREAUTH', 'BYE')

    STATUS_TRANSFORMATIONS = {
        'MESSAGES': int, 'RECENT': int, 'UNSEEN': int
    }

    def __init__(self):
        self.tags = {}
        self.queued = []
        self.authenticators = {}
    
    def registerAuthenticator(self, name, auth):
        """Register an new form of authentication
        
        When invoking the authenticate() method of IMAP4Client, the first
        matching authentication scheme found will be used.  The ordering is
        that in which the server lists support authentication schemes.
        
        @type name: C{str}
        @param name: The authentication type to associate
        
        @type auth: Implementor of C{IClientAuthentication}
        @param auth: The object to use to perform the client
        side of this authentication scheme.
        """
        self.authenticators[name.upper()] = auth

    def lineReceived(self, line):
        # print 'C: ' + line
        rest = None
        parts = line.split(None, 1)
        if len(parts) == 2:
            tag, rest = parts
        else:
            # XXX - This is rude.
            self.transport.loseConnection()
            raise IllegalServerResponse(line)
        
        self.dispatchCommand(tag, rest)

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
                log.deferr()
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
                # XXX - This is rude.
                self.transport.loseConnection()
                raise IllegalServerResponse(tag + ' ' + rest)
            else:
                if tag == '+':
                    d, lines, continuation = self.tags[self.waiting]
                    continuation.callback(lines)
                    self.tags[self.waiting] = (d, lines, None)
                else:
                    self.tags[self.waiting][1].append(rest)
        else:
            try:
                d, lines, _ = self.tags[tag]
            except KeyError:
                # XXX - This is rude.
                self.transport.loseConnection()
                raise IllegalServerResponse(tag + ' ' + rest)
            else:
                status, line = rest.split(None, 1)
                if status == 'OK':
                    # Give them this last line, too
                    d.callback((lines, rest))
                else:
                    d.errback(IMAP4Exception(line))
                del self.tags[tag]
                self.waiting = None
                self._flushQueue()
    
    def _flushQueue(self):
        if self.queued:
            d, t, command, args, continuation = self.queued.pop(0)
            self.tags[t] = (d, [], continuation)
            self.sendLine(' '.join((t, command, args)))
            self.waiting = t

    def sendCommand(self, command, args = '', continuation=None):
        d = defer.Deferred()
        t = self.makeTag()
        if self.waiting:
            self.queued.append((d, t, command, args, continuation))
            return d
        self.tags[t] = (d, [], continuation)
        self.sendLine(' '.join((t, command, args)))
        self.waiting = t
        return d

    def getCapabilities(self):
        """Request the capabilities available on this server.
        
        This command is allowed in any state of connection.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with a
        dictionary mapping capability types to lists of supported
        mechanisms, or to None if a support list is not applicable.
        """
        if self._capCache is not None:
            return defer.succeed(self._capCache)
        d = self.sendCommand('CAPABILITY')
        d.addCallback(self._cbCapabilities)
        return d
    
    def _cbCapabilities(self, (lines, tagline)):
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
        d = self.sendCommand('LOGOUT')
        d.addCallback(self._cbLogout)
        return d
    
    def _cbLogout(self, (lines, tagline)):
        # We don't particularly care what the server said
        return None
    
    
    def noop(self):
        """Perform no operation.
        
        This command is allowed in any state of connection.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with a list
        of untagged status updates the server responds with.
        """
        d = self.sendCommand('NOOP')
        d.addCallback(self._cbNoop)
        return d
    
    def _cbNoop(self, (lines, tagline)):
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
        d.addCallback(getAuthMethods).addCallback(self._cbAuthenticate, secret)
        return d

    def _cbAuthenticate(self, auths, secret):
        for scheme in auths:
            if self.authenticators.has_key(scheme):
                break
        else:
            raise NoSupportedAuthentication(auths, self.authenticators.keys())
        
        d = self.sendCommand('AUTHENTICATE', scheme)
        d.addCallback(self._cbAnswerAuth, scheme, secret)
        return d
    
    def _cbAnswerAuth(self, (lines, tagline), scheme, secret):
        auth = self.authenticators[scheme]
        self.sendLine(auth.challengeResponse(secret, lines))
    
    def login(self, username, password):
        """Authenticate with the server using a username and password
        
        This command is allowed in the Non-Authenticated state.
        
        @type username: C{str}
        @param username: The username to log in with

        @type password: C{str}
        @param password: The password to log in with

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if login is successful
        and whose errback is invoked otherwise.
        """
        return self.sendCommand('LOGIN', ' '.join((username, password)))
    
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
        d = self.sendCommand('SELECT', mailbox)
        d.addCallback(self._cbSelect)
        return d
    
    def examine(self, mailbox):
        """Select a mailbox in read-only mode
        
        This command is allowed in the Authenticated and Selected states.
        
        @type: mailbox: C{str}
        @param mailbox: The name of the mailbox to examine
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with mailbox
        information if the examine is successful and whose errback
        is invoked otherwise.
        """
        d = self.sendCommand('EXAMINE', mailbox)
        d.addCallback(self._cbSelect)
        return d
    
    def _cbSelect(self, (lines, tagline)):
        # In the absense of specification, we are free to assume:
        #   READ-WRITE access
        datum = {'READ-WRITE': 1}
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
                datum['FLAGS']= tuple(parseNestedParens(split[1])[0])
            elif split[0].upper().strip() == 'OK':
                begin = parts.find('[')
                end = parts.find(']')
                if begin == -1 or end == -1:
                    raise IllegalServerResponse(line)
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
                                datum['UID'] = int(content[1])
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
        return self.sendCommand('CREATE', name)
    
    def delete(self, name):
        """Delete a mailbox
        
        This command is allowed in the Authenticated and Selected states.
        
        @type name: C{str}
        @param name: The name of the mailbox to delete.
        
        @rtype: C{Deferred}
        @return: A deferred whose calblack is invoked if the mailbox is
        deleted successfully and whose errback is invoked otherwise.
        """
        return self.sendCommand('DELETE', name)
    
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
        return self.sendCommand('RENAME', ' '.join((oldname, newname)))
    
    def subscribe(self, name):
        """Add a mailbox to the subscription list
        
        This command is allowed in the Authenticated and Selected states.
        
        @type name: C{str}
        @param name: The mailbox to mark as 'active' or 'subscribed'
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the subscription
        is successful and whose errback is invoked otherwise.
        """
        return self.sendCommand('SUBSCRIBE', name)

    def unsubscribe(self, name):
        """Remove a mailbox from the subscription list
        
        This command is allowed in the Authenticated and Selected states.
        
        @type name: C{str}
        @param name: The mailbox to unsubscribe
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the unsubscription
        is successful and whose errback is invoked otherwise.
        """
        return self.sendCommand('UNSUBSCRIBE', name)
    
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
        d = self.sendCommand('LIST', '"%s" "%s"' % (reference, wildcard))
        d.addCallback(self._cbList, 'LIST')
        return d
    
    def lsub(self, reference, wildcard):
        """List a subset of the subscribed available mailboxes
        
        This command is allowed in the Authenticated and Selected states.
        
        The parameters and returned object are the same as for the C{list}
        method, with one slight difference: Only mailboxes which have been
        subscribed can be included in the resulting list.
        """
        d = self.sendCommand('LSUB', '"%s" "%s"' % (reference, wildcard))
        d.addCallback(self._cbList, 'LSUB')
        return d

    def _cbList(self, (lines, last), command):
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
        d = self.sendCommand('STATUS', "%s (%s)" % (mailbox, ' '.join(names)))
        d.addCallback(self._cbStatus)
        return d
    
    def _cbStatus(self, (lines, last)):
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

        @type message: C{str}
        @param message: The message to add, in RFC822 format.
        
        @type flags: Any iterable of C{str}
        @param flags: The flags to associated with this message.
        
        @type date: C{str}
        @param data: The date to associate with this message.
        """
        L = len(message)
        fmt = '%s (%s)%s%s {%d}'
        if date:
            date = '"%s"' % date
        cmd = fmt % (mailbox, ' '.join(flags), date and ' ' or '', date, L)
        continuation = defer.Deferred()
        continuation.addCallback(self._cbContinueAppend, message)
        d = self.sendCommand('APPEND', cmd, continuation)
        d.addCallback(self._cbAppend)
        return d
    
    def _cbContinueAppend(self, lines, message):
        self.transport.write(message)
    
    def _cbAppend(self, result):
        return None
    
    def check(self):
        """Tell the server to perform a checkpoint
        
        This command is allowed in the Selected state.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked when this command
        succeeds or whose errback is invoked if it fails.
        """
        return self.sendCommand('CHECK')
    
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
        return self.sendCommand('CLOSE')
    
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
        d = self.sendCommand('EXPUNGE')
        d.addCallback(self._cbExpunge)
        return d
    
    def _cbExpunge(self, (lines, last)):
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
    
    def search(self, *queries):
        """Search messages in the currently selected mailbox
        
        This command is allowed in the Selected state.
        
        Any non-zero number of queries are accepted by this method, as
        returned by the C{Query}, C{Or}, and C{Not} functions.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with a list of all
        the message sequence numbers return by the search, or whose errback
        will be invoked if there is an error.
        """
        d = self.sendCommand('SEARCH', ' '.join(queries))
        d.addCallback(self._cbSearch)
        return d
    
    def _cbSearch(self, (lines, end)):
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
        message numbers to message identifiers, or whose errback is invoked
        if there is an error.
        """
        d = self._fetch(messages, uid=1)
        d.addCallback(self._cbFetch, lookFor=('UID',))
        return d
    
    def fetchFlags(self, messages):
        """Retrieve the flags for one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set (e.g., '1,3,4' or '2:5,11')
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to lists of flags, or whose errback is invoked if
        there is an error.
        """
        d = self._fetch(messages, flags=1)
        d.addCallback(self._cbFetch, lookFor=('FLAGS',))
        return d

    def fetchInternalDate(self, messages):
        """Retrieve the internal date associated with one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to date strings, or whose errback is invoked
        if there is an error.
        """
        d = self._fetch(messages, internaldate=1)
        d.addCallback(self._cbFetch, lookFor=('INTERNALDATE',))
        return d

    def fetchEnvelope(self, messages):
        """Retrieve the envelope data for one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to envelope data, or whose errback is invoked
        if there is an error.
        """
        d = self._fetch(messages, envelope=1)
        d.addCallback(self._cbFetch, lookFor=('ENVELOPE',))
        return d

    def fetchBodyStructure(self, messages):
        """Retrieve the structure of the body of one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to structure data, or whose errback is invoked
        if there is an error.
        """
        d = self._fetch(messages, bodystructure=1)
        d.addCallback(self._cbFetch, lookFor=('BODYSTRUCTURE',))
        return d

    def fetchSimplifiedBody(self, messages):
        """Retrieve the simplified body structure of one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to body data, or whose errback is invoked
        if there is an error.
        """
        d = self._fetch(messages, body=1)
        d.addCallback(self._cbFetch, lookFor=('BODY',))
        return d

    def fetchMessage(self, messages):
        """Retrieve one or more entire messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to messages objects, or whose errback is invoked
        if there is an error.
        """
        d = self._fetch(messages, rfc822=1)
        d.addCallback(self._cbFetch, lookFor=('RFC822',))
        return d

    def fetchHeaders(self, messages):
        """Retrieve headers of one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dicts of message headers, or whose errback is
        invoked if there is an error.
        """
        d = self._fetch(messages, rfc822header=1)
        d.addCallback(self._cbFetch, lookFor=('RFC822.HEADER',))
        return d

    def fetchBody(self, messages):
        """Retrieve body text of one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to body text, or whose errback is invoked if there
        is an error.
        """
        d = self._fetch(messages, rfc822text=1)
        d.addCallback(self._cbFetch, lookFor=('RFC822.TEXT',))
        return d

    def fetchSize(self, messages):
        """Retrieve the size, in octets, of one or more messages
        
        This command is allowed in the Selected state.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to sizes, or whose errback is invoked if there is
        an error.
        """
        d = self._fetch(message, rfc822size=1)
        d.addCallback(self._cbFetch, lookFor=('RFC822.SIZE',))
        return d

    def fetchFull(self, messages):
        """Retrieve several different fields of one or more messages
        
        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate},
        C{fetchSize}, C{fetchEnvelope}, and C{fetchSimplifiedBody}
        functions.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dict of the retrieved data values, or whose
        errback is invoked if there is an error.  They dictionary keys
        are "flags", "date", "size", "envelope", and "body".
        """
        d = self._fetch(
            messages, flags=1, internaldate=1,
            rfc822size=1, envelope=1, body=1
        )
        d.addCallback(
            self._cbFetch,
            lookFor=(
                'FLAGS', 'INTERNALDATE', 'RFC822.SIZE',
                'ENVELOPE', 'BODY'
            )
        )
        return d

    def fetchAll(self, messages):
        """Retrieve several different fields of one or more messages
        
        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate},
        C{fetchSize}, and C{fetchEnvelope} functions.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dict of the retrieved data values, or whose
        errback is invoked if there is an error.  They dictionary keys
        are "flags", "date", "size", and "envelope".
        """
        d = self._fetch(
            messages, flags=1, internaldate=1,
            rfc822size=1, envelope=1
        )
        d.addCallback(
            self._cbFetch,
            lookFor=(
                'FLAGS', 'INTERNALDATE', 'RFC822.SIZE', 'ENVELOPE'
            )
        )
        return d

    def fetchFast(self, messages):
        """Retrieve several different fields of one or more messages
        
        This command is allowed in the Selected state.  This is equivalent
        to issuing all of the C{fetchFlags}, C{fetchInternalDate}, and
        C{fetchSize} functions.
        
        @type messages: C{str}
        @param messages: A message sequence set
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a dict mapping
        message numbers to dict of the retrieved data values, or whose
        errback is invoked if there is an error.  They dictionary keys are
        "flags", "date", and "size".
        """
        d = self._fetch(
            messages, flags=1, internaldate=1, rfc822size=1
        )
        d.addCallback(
            self._cbFetch,
            lookFor=(
                'FLAGS', 'INTERNALDATE', 'RFC822.SIZE'
            )
        )
        return d

    def _cbFetch(self, (lines, last), lookFor):
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
                        if data[0] in lookFor:
                            flags.setdefault(id, []).extend(data[1])
        return flags

    def _fetch(self, messages, **terms):
        cmd = ' '.join([s.upper() for s in terms.keys()])
        d = self.sendCommand('FETCH', cmd)
        return d

_ALLOWED_SECTIONS = (
    'HEADER', 'HEADER.FIELDS', 'HEADER.FIELDS.NOT', 'MIME', 'TEXT'
)

def All():
    return 'ALL'

def Body(sectionNumber=None, sectionType=None, start=None, length=None):
    """Retrieve the body of a message
    
    @type sectionNumber: C{int}
    @param sectionNumber: The MIME-IMB section number to retrieve.
    
    @type sectionType: C{str}
    @param sectionType: The MIME-IMB section type to retrieve.  This
    must be one of HEADER, HEADER.FIELDS, HEADER.FIELDS.NOT, MIME, or
    TEXT.
    
    @type start: C{int}
    @param start: If specified, the number of octets at the beginning of
    the data to skip.  If specified, C{length} must be specified as well.
    
    @type length: C{int}
    @param length: The number of octets to retrieve.

    @rtype: C{str}
    @return: The IMAP4 query string representing this item.
    """
    cmd = 'BODY[%s]'

    assert sectionType is None or sectionType in _ALLOWED_SECTIONS

    if sectionNumber is not sectionType is not None:
        cmd = cmd % ('%d.%s' % (sectionNumber, sectionType))
    else:
        cmd = cmd % (sectionType or sectionNumber or '')
    
    assert (not not start) is (not not length)
    
    if start:
        cmd = cmd + '<%d.%d>' % (start, length)
    return cmd

class IllegalQueryError(IMAP4Exception): pass

_SIMPLE_BOOL = (
    'ALL', 'ANSWERED', 'DELETED', 'DRAFT', 'FLAGGED', 'NEW', 'OLD', 'RECENT',
    'SEEN', 'UNANSWERED', 'UNDELETED', 'UNDRAFT', 'UNFLAGGED', 'UNSEEN'
)

_NO_QUOTES = (
    'LARGER', 'SMALLER', 'UID'
)

def Query(**kwarg):
    """Create a query string
    
    Among the accepted keywords are:

        message_ids : An iterable of the sequence numbers of messages to
                      include in the search
        
        all         : If set to a true value, search all messages in the
                      current mailbox
        
        answered    : If set to a true value, search messages flagged with
                      \\Answered
        
        bcc         : A substring to search the BCC header field for
        
        before      : Search messages with an internal date before this
                      value
                      
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
        
        new         : If set to a true value, search messages flagged with
                      \\Recent but not \\Seen
        
        old         : If set to a true value, search messages not flagged with
                      \\Recent
        
        on          : Search messages with an internal date which is on this
                      date
        
        recent      : If set to a true value, search for messages flagged with
                      \\Recent
        
        seen        : If set to a true value, search for messages flagged with
                      \\Seen
        
        sentbefore  : Search for messages with an RFC822 'Date' header before
                      this date
        
        senton      : Search for messages with an RFC822 'Date' header which is
                      on this date
        
        sentsince   : Search for messages with an RFC822 'Date' header which is
                      after this date
        
        since       : Search for messages with an internal date that is after
                      this date
        
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

    @rtype: C{str}
    @return: The formatted query string
    """
    cmd = []
    for (k, v) in kwarg.items():
        k = k.upper()
        if k in _SIMPLE_BOOL and v:
           cmd.append(k)
        elif k not in _NO_QUOTES:
           cmd.extend([k, '"%s"' % (v,)])
        elif k == 'HEADER':
            cmd.extend([k, v[0], '"%s"' % (v[1],)])
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

class MismatchedNesting(Exception):
    pass

class MismatchedQuoting(Exception):
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
        result.append(s[start:])
    return result


def collapseStrings(results):
    """
    Turns a list of length-one strings and lists into a list of longer
    strings and list.  For example,
    
    ['a', 'b', ['c', 'd']] is returned as ['ab', ['cd']]
    
    @type results: C{list} of C{str} and C{list}
    @param results: The list to be collapsed
    
    @rtype: C{list} of C{str} and C{list}
    @return: A new list which is the collapsed form of C{results}
    """
    copy = []
    begun = None
    listsList = [isinstance(s, types.ListType) for s in results]

    if reduce(operator.add, listsList, 0) == 0:
        return splitQuoted(''.join(results))

    for (i, c, isList) in zip(range(len(results)), results, listsList):
        if isList:
            if begun is not None:
                copy.extend(splitQuoted(''.join(results[begun:i])))
                begun = None
            copy.append(collapseStrings(c))
        elif begun is None:
            begun = i
    if begun is not None:
        copy.extend(splitQuoted(''.join(results[begun:])))
    return copy


def parseNestedParens(s):
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
        for c in s:
            if inQuote or (c != '(' and c != ')'):
                if c == '"':
                    inQuote = not inQuote
                contentStack[-1].append(c)
            elif not inQuote:
                if c == '(':
                    contentStack.append([])
                elif c == ')':
                    contentStack[-2].append(contentStack.pop())
    except IndexError:
        raise MismatchedNesting(s)
    if len(contentStack) != 1:
        raise MismatchedNesting(s)
    return collapseStrings(contentStack[0])


class AuthenticationError(IMAP4Exception): pass

class IServerAuthentication(components.Interface):
    def generateChallenge(self, ):
        """Create a challenge string
        
        @rtype: C{str}
        @return: A string representing the challenge
        """
    
    def authenticateResponse(self, challenge, response):
        """Examine a challenge response for validity.
        
        @type challenge: C{str}
        @param challenge: The challenge string associated with this response
        
        @type response: C{str}
        @param response: The response from the client
        
        @rtype: C{int} or C{str}
        @return: Returns 1 if the response is correct, or a string if
        further interaction is required with the client.
        
        @raise: C{AuthenticationError} if the response is incorrect.
        """

class IClientAuthentication(components.Interface):
    def challengeResponse(self, secret, challenge):
        """Generate a challenge response string"""

class MailboxException(IMAP4Exception): pass

class MailboxCollision(MailboxException):
    def __str__(self):
        return 'Mailbox named %s already exists' % self.args

class NoSuchMailbox(MailboxException):
    def __str__(self):
        return 'No mailbox named %s exists' % self.args

class Account:
    mboxType = None

    mailboxes = None
    subscriptions = None

    def __init__(self):
        self.mailboxes = {}
        self.subscriptions = []
    
    def addMailbox(self, name, mbox = None):
        name = name.upper()
        if name == 'INBOX' or self.mailboxes.has_key(name):
            raise MailboxCollision, name
        if mbox is None:
            mbox = self._emptyMailbox()
        self.mailboxes[name] = mbox

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

    def _emptyMailbox(self):
        return self.mboxType()

    def select(self, name, readwrite=1):
        return self.mailboxes.get(name.upper())

    def release(self, mbox):
        pass
    
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
            raise MailboxError, "Not currently subscribed to " + name
        self.subscriptions.remove(name)
    
    def listMailboxes(self, ref, wildcard):
        ref = self._inferiorNames(ref.upper())
        wildcard = wildcardToRegexp(wildcard, '/')
        return [(i, self.mailboxes[i]) for i in ref if wildcard.match(i)] 
    
    def requestStatus(self, mailbox, names):
        mailbox = mailbox.upper()
        if not self.mailboxes.has_key(mailbox):
            raise NoSuchMailbox, mailbox
        return self.mailboxes[mailbox].requestStatus(names)


class IMailbox(components.Interface):
    def getUIDValidity(self):
        """Return the unique validity identifier for this mailbox.
        
        @rtype: C{int}
        """
    
    def getFlags(self):
        """Return the flags defined in this mailbox
        
        Flags with the \\ prefix are reserved for use as system flags.
        
        @rtype: C{list} of C{str}
        @return: A list of the flags that can be set on messages in this mailbox.
        """
    
    def getMessageCount(self):
        """Return the number of messages in this mailbox"""
    
    def getRecentCount(self):
        """Return the number of messages with the 'Recent' flag"""

    def getUnseenCount(self):
        """Return the number of messages with the 'Unseen' flag"""

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
    
    def addMessage(self, message, flags, date = None):
        """Add the given message to this mailbox.
        
        @type message: C{str}
        @param message: The RFC822 formatted message
        
        @type flags: Any iterable of C{str}
        @param flags: The flags to associate with this message
        
        @type date: C{str}
        @param date: If specified, the date to associate with this
        message.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the message
        is added successfully and whose errback is invoked otherwise.
        """

    def expunge(self):
        """Remove all messages flagged \\Deleted.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a list of
        message sequence numbers which were deleted and whose errback is
        invoked if there is an error.
        """

    def search(self, query):
        """Search for messages that meet the given query criteria.
        
        @type query: C{list}
        @param query: The search criteria
        
        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked with a list of
        message sequence numbers which match the search criteria and whose
        errback is invoked if there is an error.
        """
