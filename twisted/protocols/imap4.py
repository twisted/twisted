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


import binascii, operator, re, string, types

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
            passon = None
            if self._pendingSize < 0:
                data, passon = data[:self._pendingSize], data[self._pendingSize:]
            self._pendingBuffer.append(data)
            tag, cmd = self._pendingLiteral
            rest = ''.join(self._pendingBuffer)
            self._pendingBuffer = None
            self._pendingSize = None
            self._pendingLiteral = None
            self.dispatchCommand(tag, cmd, rest)
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
        if rest and rest[0] == '{' and rest[-1] == '}':
            try:
                octets = int(rest[1:-1])
            except ValueError:
                # XXX - This is rude.
                self.transport.loseConnection()
                raise IllegalClientResponse(line)
            else:
                if self.lookupCommand(cmd):
                    self._setupForLiteral(octets, (tag, cmd))
                    self.setRawMode()
                else:
                    self.sendBadResponse(tag, 'Unsupported command')
        else:
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
        self._respond(message, None, '')

    def sendContinuationRequest(self, msg = 'Ready for additional command text'):
        self.sendLine('+ ' + msg)

    def _setupForLiteral(self, octets, rest):
        self._pendingBuffer = []
        self._pendingSize = octets
        self._pendingLiteral = rest
        self.sendContinuationRequest('Ready for %d octets of text' % octets)

    def _respond(self, state, tag, message):
        if not tag:
            tag = '*'
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
                    d, lines = self.tags[self.waiting]
                    d.callback(lines)
                    del self.tags[self.waiting]
                    self.waiting = None
                    self._flushQueue()
                else:
                    self.tags[self.waiting][1].append(rest)
        else:
            try:
                d, lines = self.tags[tag]
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
            d, t, command, args = self.queued.pop(0)
            self.tags[t] = d, []
            self.sendLine(' '.join((t, command, args)))
            self.waiting = t

    def sendCommand(self, command, args = ''):
        d = defer.Deferred()
        t = self.makeTag()
        if self.waiting:
            self.queued.append((d, t, command, args))
            return d
        self.tags[t] = d, []
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
                datum['FLAGS']= tuple(parseNestedParens(split[1]))
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
                            datum['PERMANENTFLAGS'] = tuple(parseNestedParens(content[1]))
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

class MismatchedNesting(Exception):
    pass

class MismatchedQuoting(Exception):
    pass

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
    return collapseStrings(contentStack[0][0])


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

    def __init__(self):
        self.mailboxes = {}
    
    def addMailbox(self, name, mbox = None):
        name = name.upper()
        if name == 'INBOX' or self.mailboxes.has_key(name):
            raise MailboxCollision, name
        if mbox is None:
            mbox = self._emptyMailbox()
        self.mailboxes[name] = mbox

    def create(self, pathspec):
        paths = filter(None, pathspec.split('/'))
        for accum in range(1, len(paths) - 1):
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
        mbox = self.select(name)
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
