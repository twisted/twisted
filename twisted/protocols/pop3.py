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
import md5

from twisted.protocols import basic
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

class POP3Error(Exception):
    pass

class POP3(basic.LineReceiver):

    __implements__ = (interfaces.IProducer,)

    magic = None
    _userIs = None
    highest = 0
    
    # A reference to the newcred Portal instance we will authenticate
    # through.
    portal = None
    
    def connectionMade(self):
        if self.magic is None:
            self.magic = '<%s>' % time.time()
        self.mbox = None
        self.successResponse(self.magic)
        log.msg("New connection from " + str(self.transport.getPeer()))

    def successResponse(self, message=''):
        self.sendLine('+OK ' + str(message))

    def failResponse(self, message=''):
        self.sendLine('-ERR ' + str(message))

    def lineReceived(self, line):
        try:
            return self.processCommand(*line.split())
        except (ValueError, AttributeError, POP3Error, TypeError), e:
            log.err()
            self.failResponse('bad protocol or server: %s: %s' % (e.__class__.__name__, e))
    
    def processCommand(self, command, *args):
        command = string.upper(command)
        if self.mbox is None and command not in ('APOP', 'USER', 'PASS', 'RPOP', 'QUIT'):
            raise POP3Error("not authenticated yet: cannot do %s" % command)
        f = getattr(self, 'do_' + command, None)
        if f:
            return f(*args)
        raise POP3Error("Unknown protocol command: " + command)

    def do_APOP(self, user, digest):
        d = defer.maybeDeferred(self.authenticateUserAPOP, user, digest)
        d.addCallbacks(self._cbMailbox, self._ebMailbox, callbackArgs=(user,)
        ).addErrback(self._ebUnexpected)
    
    def _cbMailbox(self, (interface, avatar, logout), user):
        self.mbox = avatar
        self._onLogout = logout
        self.successResponse('Authentication succeeded')
        log.msg("Authenticated login for " + user)
    
    def _ebMailbox(self, failure):
        failure.trap(cred.error.LoginFailed)
        self.failResponse('Authentication failed')
        log.msg("Denied login attempt from " + str(self.transport.getPeer()))
    
    def _ebUnexpected(self, failure):
        self.failResponse('Server error: ' + failure.getErrorMessage())
        log.err(failure)

    def do_USER(self, user):
        self._userIs = user
        self.successResponse('USER accepted, send PASS')

    def do_PASS(self, password):
        user = self._userIs
        self._userIs = None
        d = defer.maybeDeferred(self.authenticateUserPASS, user, password)
        d.addCallbacks(self._cbMailbox, self._ebMailbox, callbackArgs=(user,)
        ).addErrback(self._ebUnexpected)

    def do_STAT(self):
        msg = self.mbox.listMessages()
        total = reduce(operator.add, msg, 0)
        self.successResponse('%d %d' % (len(msg), total))

    def do_LIST(self, i=None):
        messages = self.mbox.listMessages()
        self.successResponse(len(messages))
        i = 1
        for message in messages:
            if message:
                self.sendLine('%d %d' % (i, message))
            i = i+1
        self.sendLine('.')

    def do_UIDL(self, i=None):
        messages = self.mbox.listMessages()
        self.successResponse()
        for i in range(len(messages)):
            if messages[i]:
                self.sendLine('%d %s' % (i+1, self.mbox.getUidl(i)))
        self.sendLine('.')

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
        size = max(int(size), resp)
        self.successResponse(size)
        s = basic.FileSender()
        s.beginFileTransfer(fp, self.transport, self.transformChunk
        ).addCallback(self.finishedFileTransfer)
    
    def transformChunk(self, chunk):
        return chunk.replace('\n', '\r\n').replace('\r\n.', '\r\n..')

    def finishedFileTransfer(self, lastsent):
        if self.lastsent != '\n':
            line = '\r\n.'
        else:
            line = '.'
        self.sendLine('.')
        
    def do_RETR(self, i):
        self.highest = max(self.highest, i)
        resp, fp = self.getMessageFile(i)
        if not fp:
            return
        self.successResponse(resp)
        while 1:
            line = fp.readline()
            if not line:
                break
            if line[-1] == '\n':
                line = line[:-1]
            if line[:1] == '.':
                line = '.'+line
            self.sendLine(line)
        self.sendLine('.')

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
            log.deferr()
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
        @return: A deferred whose callback invoked if the login is
        successful, and whose errback will be invoked otherwise.
        """
        if self.portal is not None:
            return self.portal.login(
                APOPCredentials(self.magic, user, digest),
                None,
                IMailbox
            )
        return defer.fail(cred.error.UnauthorizedLogin())

    def authenticateUserPASS(self, user, password):
        """Perform authentication of a username/password login.
        
        @type user: C{str}
        @param user: The name of the user attempting to log in.
        
        @type password: C{str}
        @param password: The password to attempt to authenticate with.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback invoked if the login is
        successful, and whose errback will be invoked otherwise.
        """
        if self.portal is not None:
            return self.portal.login(
                cred.credentials.UsernamePassword(user, password),
                None,
                IMailbox
            )
        return defer.fail(cred.error.UnauthorizedLogin())

class IMailbox(components.Interface):
    def listMessages(self, i=None):
        """"""

    def getMessage(self, index):
        """"""
    
    def getUidl(self, index):
        """"""
    
    def deleteMessage(self, index):
        """"""
    
    def undeleteMessages(self):
        """"""
    
    def sync(self):
        """"""

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

class POP3Client(basic.LineReceiver):

    mode = SHORT
    command = 'WELCOME'
    import re
    welcomeRe = re.compile('<(.*)>')

    def sendShort(self, command, params):
        self.sendLine('%s %s' % (command, params))
        self.command = command
        self.mode = SHORT

    def sendLong(self, command, params):
        self.sendLine('%s %s' % (command, params))
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
