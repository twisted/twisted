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
    
    # The mailbox object for this connection
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
        args = line.split(None, 2)
        rest = None
        if len(args) == 3:
            tag, cmd, rest = args
        elif len(args) == 2:
            tag, cmd = args
        else:
            # XXX - This is rude.
            self.transport.loseConnection()
    
        cmd = cmd.upper()
        if rest and rest[0] == '{' and rest[-1] == '}':
            try:
                octets = int(rest[1:-1])
            except ValueError:
                # XXX - This is rude.
                self.transport.loseConnection()
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
    
    def sendUntaggedResponse(self, command, rest):
        self._respond(command, None, rest)

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
        self.sendUntaggedResponse('CAPABILITY', caps)
        self.sendPositiveResponse(tag, 'CAPABILITY completed')

    auth_CAPABILITY = unauth_CAPABILITY
    select_CAPABILITY = unauth_CAPABILITY
    logout_CAPABILITY = unauth_CAPABILITY
    
    def unauth_LOGOUT(self, tag, args):
        self.sendUntaggedResponse('BYE', 'Nice talking to you')
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
        return None
    
    def _cbLogin(self, mbox, tag):
        if mbox is None:
            self.sendNegativeResponse(tag, 'LOGIN failed')
        else:
            self.mbox = mbox
            self.sendPositiveResponse(tag, 'LOGIN succeeded')
            self.state = 'auth'
    
    def _ebLogin(self, failure, tag):
        self.sendBadResponse(tag, 'Server error: ' + str(failure.value))

class UnhandledResponse(IMAP4Exception): pass

class NegativeResponse(IMAP4Exception): pass

class NoSupportedAuthentication(IMAP4Exception):
    def __init__(self, serverSupports, clientSupports):
        IMAP4Exception.__init__(self, 'No supported authentication schemes available')
        self.serverSupports = serverSupports
        self.clientSupports = clientSupports

class IMAP4Client(basic.LineReceiver):
    tags = None
    ambiguity = None
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
        rest = None
        parts = line.split(None, 2)
        if len(parts) == 3:
            tag, status, rest = parts
        elif len(parts) == 2:
            tag, status = parts
        else:
            # XXX - This is rude.
            self.transport.loseConnection()
        
        status = status.upper()
        self.dispatchCommand(tag, status, rest)

    def makeTag(self):
        tag = '%0.4X' % self.tagID
        self.tagID += 1
        return tag

    def dispatchCommand(self, tag, command, rest):
        if command in self.STATUS_CODES:
            f = getattr(self, 'status_' + command)
            f(tag, rest)
        elif tag == '*' and self.ambiguity:
            self.tags[self.ambiguity][1].append((command, rest))
        elif tag == '+':
            d, lines = self.tags[self.ambiguity]
            del self.tags[self.ambiguity]
            d.callback(lines)
        else:
            pass

    def status_OK(self, tag, args):
        if self.state is None:
            self.state = 'unauth'
        elif tag != '*' and tag != '+':
            try:
                d, lines = self.tags[tag]
            except KeyError:
                # XXX - This is rude
                self.transport.loseConnection()
            else:
                del self.tags[tag]
                d.callback(lines)

    def status_PREAUTH(self, tag, args):
        self.state = 'auth'
    
    def status_BYE(self, tag, args):
        self.state = 'logout'
    
    def status_BAD(self, tag, args):
        try:
            self.tags[tag][0].errback(UnhandledResponse(args))
        except KeyError:
            # XXX
            log.msg(tag + ' ' + args)
        else:
            del self.tags[tag]

    def status_NO(self, tag, args):
        try:
            self.tags[tag][0].errback(NegativeResponse(args))
        except KeyError:
            # XXX
            log.msg(tag + ' ' + args)
        else:
            del self.tags[tag]

    def sendCommand(self, command, args = '', ambiguous = 0):
        if self.ambiguity:
            self.queued.append((command, args, ambiguous))
            return
        d = defer.Deferred()
        t = self.makeTag()
        self.tags[t] = d, []
        self.sendLine(' '.join((t, command, args)))
        if ambiguous:
            self.ambiguity = t
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
        d = self.sendCommand('CAPABILITY', ambiguous=1)
        d.addCallback(self._cbCapabilities)
        return d
    
    def _cbCapabilities(self, lines):
        caps = {}
        for (cmd, rest) in lines:
            rest = rest.split()
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
        d = self.sendCommand('LOGOUT', ambiguous=1)
        d.addCallback(self._cbLogout)
        return d
    
    def _cbLogout(self, lines):
        # We don't particularly care what the server said
        return None
    
    
    def noop(self):
        """Perform no operation.
        
        This command is allowed in any state of connection.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked with a list
        of untagged status updates the server responds with.
        """
        d = self.sendCommand('NOOP', ambiguous=1)
        d.addCallback(self._cbNoop)
        return d
    
    def _cbNoop(self, lines):
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
        
        d = self.sendCommand('AUTHENTICATE', scheme, ambiguous=1)
        d.addCallback(self._cbAnswerAuth, scheme, secret)
        return d
    
    def _cbAnswerAuth(self, lines, scheme, secret):
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
        return self.sendCommand('LOGIN', ' '.join((username, password)), 1)


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
