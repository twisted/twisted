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
"""


from twisted.protocols import basic
import os, time, string, operator, stat, md5, binascii
from twisted.internet import protocol
from twisted.python import components, log

class POP3Error(Exception):
    pass

class POP3(basic.LineReceiver):

    magic = None
    _userIs = None
    highest = 0

    def connectionMade(self):
        if self.magic is None:
            self.magic = '<%s>' % time.time()
        self.mbox = None
        self.successResponse(self.magic)

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
        self.mbox = self.authenticateUserAPOP(user, digest)
        if not self.mbox:
            raise POP3Error("Invalid APOP response")
        self.successResponse('Authentication succeeded')

    def do_USER(self, user):
        self._userIs = user
        self.successResponse('USER accepted, send PASS')

    def do_PASS(self, password):
        user = self._userIs
        self._userIs = None
        self.mbox = self.authenticateUserPASS(user, password)
        if not self.mbox:
            raise POP3Error("Authentication failed")
        self.successResponse('Authentication succeeded')

    def do_STAT(self):
        msg = self.mbox.listMessages()
        total = reduce(operator.add, msg, 0)
        self.successResponse('%d %d' % (len(msg), total))

    def do_LIST(self, i=None):
        messages = self.mbox.listMessages()
        total = reduce(operator.add, messages, 0)
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
        while size:
            line = fp.readline()
            if not line:
                break
            if line[-1] == '\n':
                line = line[:-1]
            if line[:1] == '.':
                line = '.'+line
            self.sendLine(line[:size])
            size = size-len(line[:size])
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
        self.successReponse()
    
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
        """Stub for APOP authentication.
        
        Override this to perform some useful operation
        """
        return Mailbox()

    def authenticateUserPASS(self, user, password):
        """Stub for USER/PASS authentication.
        
        Override this to perform some useful operation
        """
        return Mailbox()


class IMailbox(components.Interface):
    
    def listMessages(self, i=None):
        """"""

    def getMessage(self, index):
        """"""
    
    def getUidl(self, index):
        """"""
    
    def deleteMessage(self, index):
        """"""
    
    def undeleteMessage(self, index):
        """"""
    
    def sync(self):
        """"""

class Mailbox:

    def listMessages(self):
        return []
    def getMessage(self, i):
        raise ValueError
    def getUidl(self, i):
        raise ValueError
    def deleteMessage(self, i):
        raise ValueError
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
            from twisted.python import log
            log.deferr()

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

    def apopAuthenticate(self, user, password):
        digest = md5.new(magic+password).digest()
        digest = string.join(map(lambda x: "%02x"%ord(x), digest), '')
        self.apop(user, digest)

    def apop(self, user, digest):
        self.sendLong('APOP', user+' '+digest)
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
