# -*- test-case-name: twisted.test.test_pop3 -*-
#
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

"""Post-office Protocol version 3

@author U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
@author U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}

API Stability: Unstable
"""

import time
import string
import operator
import base64
import binascii
import md5

from twisted.protocols import smtp
from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import interfaces
from twisted.python import components
from twisted.python import log

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials

##
## Authentication
##
class APOPCredentials:
    __implements__ = (cred.credentials.IUsernamePassword,)

    def __init__(self, magic, username, digest):
        self.magic = magic
        self.username = username
        self.digest = digest

    def checkPassword(self, password):
        seed = self.magic + password
        my_digest = md5.new(seed).hexdigest()
        if my_digest == self.digest:
            return True
        return False
##

class _HeadersPlusNLines:
    def __init__(self, f, n):
        self.f = f
        self.n = n
        self.linecount = 0
        self.headers = 1
        self.done = 0
        self.buf = ''

    def read(self, bytes):
        if self.done:
            return ''
        data = self.f.read(bytes)
        if not data:
            return data
        if self.headers:
            df, sz = data.find('\r\n\r\n'), 4
            if df == -1:
                df, sz = data.find('\n\n'), 2
            if df!=-1:
                df += sz
                val = data[:df]
                data = data[df:]
                self.linecount = 1
                self.headers = 0
        else:
            val = ''
        if self.linecount > 0:
            dsplit = (self.buf+data).split('\n')
            self.buf = dsplit[-1]
            for ln in dsplit[:-1]:
                if self.linecount > self.n:
                    self.done = 1
                    return val
                val += (ln + '\n')
                self.linecount += 1
            return val
        else:
            return data


class POP3Error(Exception):
    pass

class POP3(basic.LineOnlyReceiver, policies.TimeoutMixin):

    __implements__ = (interfaces.IProducer,)

    magic = None
    _userIs = None
    _onLogout = None
    highest = 0

    AUTH_CMDS = ['CAPA', 'USER', 'PASS', 'APOP', 'AUTH', 'RPOP', 'QUIT']

    # A reference to the newcred Portal instance we will authenticate
    # through.
    portal = None

    # Who created us
    factory = None

    # The mailbox we're serving
    mbox = None

    # Set this pretty low -- POP3 clients are expected to log in, download
    # everything, and log out.
    timeOut = 300

    # Current protocol state
    state = "COMMAND"

    # PIPELINE
    blocked = None

    def connectionMade(self):
        if self.magic is None:
            self.magic = self.generateMagic()
        self.successResponse(self.magic)
        self.setTimeout(self.timeOut)
        log.msg("New connection from " + str(self.transport.getPeer()))

    def connectionLost(self, reason):
        if self._onLogout is not None:
            self._onLogout()
            self._onLogout = None
        self.setTimeout(None)

    def generateMagic(self):
        return smtp.messageid()

    def successResponse(self, message=''):
        self.sendLine('+OK ' + str(message))

    def failResponse(self, message=''):
        self.sendLine('-ERR ' + str(message))

#    def sendLine(self, line):
#        print 'S:', repr(line)
#        basic.LineOnlyReceiver.sendLine(self, line)

    def lineReceived(self, line):
#        print 'C:', repr(line)
        self.resetTimeout()
        getattr(self, 'state_' + self.state)(line)

    def _unblock(self, _):
        commands = self.blocked
        self.blocked = None
        while commands and self.blocked is None:
            cmd, args = commands.pop(0)
            self.processCommand(cmd, *args)
        if self.blocked is not None:
            self.blocked.extend(commands)

    def state_COMMAND(self, line):
        try:
            return self.processCommand(*line.split())
        except (ValueError, AttributeError, POP3Error, TypeError), e:
            log.err()
            self.failResponse('bad protocol or server: %s: %s' % (e.__class__.__name__, e))

    def processCommand(self, command, *args):
        if self.blocked is not None:
            self.blocked.append((command, args))
            return

        command = string.upper(command)
        authCmd = command in self.AUTH_CMDS
        if not self.mbox and not authCmd:
            raise POP3Error("not authenticated yet: cannot do " + command)
        f = getattr(self, 'do_' + command, None)
        if f:
            return f(*args)
        raise POP3Error("Unknown protocol command: " + command)


    def listCapabilities(self):
        baseCaps = [
            "TOP",
            "USER",
            "UIDL",
            "PIPELINE",
            "CELERITY",
            "AUSPEX",
            "POTENCE",
        ]

        if components.implements(self.factory, IServerFactory):
            # Oh my god.  We can't just loop over a list of these because
            # each has spectacularly different return value semantics!
            try:
                v = self.factory.cap_IMPLEMENTATION()
            except NotImplementedError:
                pass
            except:
                log.err()
            else:
                baseCaps.append("IMPLEMENTATION " + str(v))

            try:
                v = self.factory.cap_EXPIRE()
            except NotImplementedError:
                pass
            except:
                log.err()
            else:
                if v is None:
                    v = "NEVER"
                if self.factory.perUserExpiration():
                    if self.mbox:
                        v = str(self.mbox.messageExpiration)
                    else:
                        v = str(v) + " USER"
                v = str(v)
                baseCaps.append("EXPIRE " + v)

            try:
                v = self.factory.cap_LOGIN_DELAY()
            except NotImplementedError:
                pass
            except:
                log.err()
            else:
                if self.factory.perUserLoginDelay():
                    if self.mbox:
                        v = str(self.mbox.loginDelay)
                    else:
                        v = str(v) + " USER"
                v = str(v)
                baseCaps.append("LOGIN-DELAY " + v)

            try:
                v = self.factory.challengers
            except AttributeError:
                pass
            except:
                log.err()
            else:
                baseCaps.append("SASL " + ' '.join(v.keys()))
        return baseCaps

    def do_CAPA(self):
        self.successResponse("I can do the following:")
        for cap in self.listCapabilities():
            self.sendLine(cap)
        self.sendLine(".")

    def do_AUTH(self, args=None):
        if not getattr(self.factory, 'challengers', None):
            self.failResponse("AUTH extension unsupported")
            return

        if args is None:
            self.successResponse("Supported authentication methods:")
            for a in self.factory.challengers:
                self.sendLine(a.upper())
            self.sendLine(".")
            return

        auth = self.factory.challengers.get(args.strip().upper())
        if not self.portal or not auth:
            self.failResponse("Unsupported SASL selected")
            return

        self._auth = auth()
        chal = self._auth.getChallenge()

        self.sendLine('+ ' + base64.encodestring(chal).rstrip('\n'))
        self.state = 'AUTH'

    def state_AUTH(self, line):
        self.state = "COMMAND"
        try:
            parts = base64.decodestring(line).split(None, 1)
        except binascii.Error:
            self.failResponse("Invalid BASE64 encoding")
        else:
            if len(parts) != 2:
                self.failResponse("Invalid AUTH response")
                return
            self._auth.username = parts[0]
            self._auth.response = parts[1]
            d = self.portal.login(self._auth, None, IMailbox)
            d.addCallback(self._cbMailbox, parts[0])
            d.addErrback(self._ebMailbox)
            d.addErrback(self._ebUnexpected)

    def do_APOP(self, user, digest):
        d = defer.maybeDeferred(self.authenticateUserAPOP, user, digest)
        d.addCallbacks(self._cbMailbox, self._ebMailbox, callbackArgs=(user,)
        ).addErrback(self._ebUnexpected)

    def _cbMailbox(self, (interface, avatar, logout), user):
        if interface is not IMailbox:
            self.failResponse('Authentication failed')
            log.err("_cbMailbox() called with an interface other than IMailbox")
            return

        self.mbox = avatar
        self._onLogout = logout
        self.successResponse('Authentication succeeded')
        log.msg("Authenticated login for " + user)

    def _ebMailbox(self, failure):
        failure = failure.trap(cred.error.LoginDenied, cred.error.LoginFailed)
        if issubclass(failure, cred.error.LoginDenied):
            self.failResponse("Access denied: " + str(failure))
        elif issubclass(failure, cred.error.LoginFailed):
            self.failResponse('Authentication failed')
        log.msg("Denied login attempt from " + str(self.transport.getPeer()))

    def _ebUnexpected(self, failure):
        self.failResponse('Server error: ' + failure.getErrorMessage())
        log.err(failure)

    def do_USER(self, user):
        self._userIs = user
        self.successResponse('USER accepted, send PASS')

    def do_PASS(self, password):
        if self._userIs is None:
            self.failResponse("USER required before PASS")
            return
        user = self._userIs
        self._userIs = None
        d = defer.maybeDeferred(self.authenticateUserPASS, user, password)
        d.addCallbacks(self._cbMailbox, self._ebMailbox, callbackArgs=(user,)
        ).addErrback(self._ebUnexpected)

    def do_STAT(self):
        i = 0
        sum = 0
        msg = self.mbox.listMessages()
        for e in msg:
            i += 1
            sum += e
        self.successResponse('%d %d' % (i, sum))

    def do_LIST(self, i=None):
        if i is None:
            messages = self.mbox.listMessages()
            lines = []
            for msg in messages:
                lines.append('%d %d%s' % (len(lines) + 1, msg, self.delimiter))
            self.successResponse(len(lines))
            self.transport.writeSequence(lines)
            self.sendLine('.')
        else:
            msg = self.mbox.listMessages(int(i) - 1)
            self.successResponse(str(msg))

    def do_UIDL(self, i=None):
        if i is None:
            messages = self.mbox.listMessages()
            self.successResponse()
            i = 0
            lines = []
            for msg in messages:
                if msg:
                    uid = self.mbox.getUidl(i)
                    lines.append('%d %s%s' % (i + 1, uid, self.delimiter))
                i += 1
            self.transport.writeSequence(lines)
            self.sendLine('.')
        else:
            msg = self.mbox.getUidl(int(i) - 1)
            self.successResponse(str(msg))

    def getMessageFile(self, i):
        i = int(i) - 1
        try:
            resp = self.mbox.listMessages(i)
        except (IndexError, ValueError), e:
            self.failResponse('index out of range')
            return None, None
        if not resp:
            self.failResponse('message deleted')
            return None, None
        return resp, self.mbox.getMessage(i)

    def do_TOP(self, i, size):
        self.highest = max(self.highest, i)
        resp, fp = self.getMessageFile(i)
        if not fp:
            return
        size = int(size)
        fp = _HeadersPlusNLines(fp, size)
        self.successResponse("Top of message follows")
        s = basic.FileSender()
        self.blocked = []
        s.beginFileTransfer(fp, self.transport, self.transformChunk
            ).addCallback(self.finishedFileTransfer
            ).addCallback(self._unblock
            ).addErrback(log.err
            )

    def do_RETR(self, i):
        self.highest = max(self.highest, i)
        resp, fp = self.getMessageFile(i)
        if not fp:
            return
        self.successResponse(resp)
        s = basic.FileSender()
        self.blocked = []
        s.beginFileTransfer(fp, self.transport, self.transformChunk
            ).addCallback(self.finishedFileTransfer
            ).addCallback(self._unblock
            ).addErrback(log.err
            )

    def transformChunk(self, chunk):
        return chunk.replace('\n', '\r\n').replace('\r\n.', '\r\n..')

    def finishedFileTransfer(self, lastsent):
        if lastsent != '\n':
            line = '\r\n.'
        else:
            line = '.'
        self.sendLine(line)

    def do_DELE(self, i):
        i = int(i)-1
        self.mbox.deleteMessage(i)
        self.successResponse()

    def do_NOOP(self):
        """Perform no operation.  Return a success code"""
        self.successResponse()

    def do_RSET(self):
        """Unset all deleted message flags"""
        try:
            self.mbox.undeleteMessages()
        except:
            log.err()
            self.failResponse()
        else:
            self.highest = 1
            self.successResponse()

    def do_LAST(self):
        """Respond with the highest message access thus far"""
        # omg this is such a retarded protocol
        self.successResponse(self.highest)

    def do_RPOP(self, user):
        self.failResponse('permission denied, sucker')

    def do_QUIT(self):
        if self.mbox:
            self.mbox.sync()
        self.successResponse()
        self.transport.loseConnection()

    def authenticateUserAPOP(self, user, digest):
        """Perform authentication of an APOP login.

        @type user: C{str}
        @param user: The name of the user attempting to log in.

        @type digest: C{str}
        @param digest: The response string with which the user replied.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the login is
        successful, and whose errback will be invoked otherwise.  The
        callback will be passed a 3-tuple consisting of IMailbox,
        an object implementing IMailbox, and a zero-argument callable
        to be invoked when this session is terminated.
        """
        if self.portal is not None:
            return self.portal.login(
                APOPCredentials(self.magic, user, digest),
                None,
                IMailbox
            )
        raise cred.error.UnauthorizedLogin()

    def authenticateUserPASS(self, user, password):
        """Perform authentication of a username/password login.

        @type user: C{str}
        @param user: The name of the user attempting to log in.

        @type password: C{str}
        @param password: The password to attempt to authenticate with.

        @rtype: C{Deferred}
        @return: A deferred whose callback is invoked if the login is
        successful, and whose errback will be invoked otherwise.  The
        callback will be passed a 3-tuple consisting of IMailbox,
        an object implementing IMailbox, and a zero-argument callable
        to be invoked when this session is terminated.
        """
        if self.portal is not None:
            return self.portal.login(
                cred.credentials.UsernamePassword(user, password),
                None,
                IMailbox
            )
        raise cred.error.UnauthorizedLogin()

class IServerFactory(components.Interface):
    """Interface for querying additional parameters of this POP3 server.

    Any cap_* method may raise NotImplementedError if the particular
    capability is not supported.  If cap_EXPIRE() does not raise
    NotImplementedError, perUserExpiration() must be implemented, otherwise
    they are optional.  If cap_LOGIN_DELAY() is implemented,
    perUserLoginDelay() must be implemented, otherwise they are optional.

    @ivar challengers: A dictionary mapping challenger names to classes
    implementing C{IUsernameHashedPassword}.
    """

    def cap_IMPLEMENTATION(self):
        """Return a string describing this POP3 server implementation."""

    def cap_EXPIRE(self):
        """Return the minimum number of days messages are retained."""

    def perUserExpiration(self):
        """Indicate whether message expiration is per-user.

        @return: True if it is, false otherwise.
        """

    def cap_LOGIN_DELAY(self):
        """Return the minimum number of seconds between client logins."""

    def perUserLoginDelay(self):
        """Indicate whether the login delay period is per-user.

        @return: True if it is, false otherwise.
        """

class IMailbox(components.Interface):
    """
    @type loginDelay: C{int}
    @ivar loginDelay: The number of seconds between allowed logins for the
    user associated with this mailbox.  None

    @type messageExpiration: C{int}
    @ivar messageExpiration: The number of days messages in this mailbox will
    remain on the server before being deleted.
    """

    def listMessages(self, index=None):
        """Retrieve the size of one or more messages.

        @type index: C{int} or C{None}
        @param index: The number of the message for which to retrieve the
        size (starting at 0), or None to retrieve the size of all messages.

        @rtype: C{int} or any iterable of C{int}
        @return: The number of octets in the specified message, or an
        iterable of integers representing the number of octets in all the
        messages.
        """

    def getMessage(self, index):
        """Retrieve a file-like object for a particular message.

        @type index: C{int}
        @param index: The number of the message to retrieve

        @rtype: A file-like object
        """

    def getUidl(self, index):
        """Get a unique identifier for a particular message.

        @type index: C{int}
        @param index: The number of the message for which to retrieve a UIDL

        @rtype: C{str}
        @return: A string of printable characters uniquely identifying for all
        time the specified message.
        """

    def deleteMessage(self, index):
        """Delete a particular message.

        This must not change the number of messages in this mailbox.  Further
        requests for the size of deleted messages should return 0.  Further
        requests for the message itself may raise an exception.

        @type index: C{int}
        @param index: The number of the message to delete.
        """

    def undeleteMessages(self):
        """Undelete any messages possible.

        If a message can be deleted it, it should return it its original
        position in the message sequence and retain the same UIDL.
        """

    def sync(self):
        """Perform checkpointing.

        This method will be called to indicate the mailbox should attempt to
        clean up any remaining deleted messages.
        """

class Mailbox:
    __implements__ = (IMailbox,)

    def listMessages(self, i=None):
        return []
    def getMessage(self, i):
        raise ValueError
    def getUidl(self, i):
        raise ValueError
    def deleteMessage(self, i):
        raise ValueError
    def undeleteMessages(self):
        pass
    def sync(self):
        pass

NONE, SHORT, FIRST_LONG, LONG = range(4)

NEXT = {}
NEXT[NONE] = NONE
NEXT[SHORT] = NONE
NEXT[FIRST_LONG] = LONG
NEXT[LONG] = NONE

class POP3Client(basic.LineOnlyReceiver):

    mode = SHORT
    command = 'WELCOME'
    import re
    welcomeRe = re.compile('<(.*)>')

    def sendShort(self, command, params):
        self.sendLine('%s %s' % (command, params))
        self.command = command
        self.mode = SHORT

    def sendLong(self, command, params):
        if params:
            self.sendLine('%s %s' % (command, params))
        else:
            self.sendLine(command)
        self.command = command
        self.mode = FIRST_LONG

    def handle_default(self, line):
        if line[:-4] == '-ERR':
            self.mode = NONE

    def handle_WELCOME(self, line):
        code, data = line.split(' ', 1)
        if code != '+OK':
            self.transport.loseConnection()
        else:
            m = self.welcomeRe.match(line)
            if m:
                self.welcomeCode = m.group(1)

    def _dispatch(self, command, default, *args):
        try:
            method = getattr(self, 'handle_'+command, default)
            if method is not None:
                method(*args)
        except:
            log.err()

    def lineReceived(self, line):
        if self.mode == SHORT or self.mode == FIRST_LONG:
            self.mode = NEXT[self.mode]
            self._dispatch(self.command, self.handle_default, line)
        elif self.mode == LONG:
            if line == '.':
                self.mode = NEXT[self.mode]
                self._dispatch(self.command+'_end', None)
                return
            if line[:1] == '.':
                line = line[1:]
            self._dispatch(self.command+"_continue", None, line)

    def apopAuthenticate(self, user, password, magic):
        digest = md5.new(magic + password).hexdigest()
        self.apop(user, digest)

    def apop(self, user, digest):
        self.sendLong('APOP', ' '.join((user, digest)))
    def retr(self, i):
        self.sendLong('RETR', i)
    def dele(self, i):
        self.sendShort('DELE', i)
    def list(self, i=''):
        self.sendLong('LIST', i)
    def uidl(self, i=''):
        self.sendLong('UIDL', i)
    def user(self, name):
        self.sendShort('USER', name)
    def pass_(self, pass_):
        self.sendShort('PASS', pass_)
    def quit(self):
        self.sendShort('QUIT', '')
