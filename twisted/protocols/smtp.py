
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

"""Simple Mail Transfer Protocol implementation.
"""

from twisted.protocols import basic
import protocol
import os, time, string, operator

class SMTPError(Exception):
    pass

COMMAND, DATA = range(2)

class User:

    def __init__(self, destination, helo, protocol, orig):
        try:
            self.name, self.domain = string.split(destination, '@', 1)
        except ValueError:
            self.name = destination
            self.domain = ''
        self.helo = helo
        self.protocol = protocol
        self.orig = orig

class SMTP(basic.LineReceiver):

    def __init__(self):
        self.mode = COMMAND
        self.__from = None
        self.__helo = None
        self.__to = ()

    def connectionMade(self):
        self.sendCode(220, 'Spammers beware, your ass is on fire')

    def sendCode(self, code, message=''):
        "Send an SMTP code with a message."
        self.transport.write('%d %s\r\n' % (code, message))

    def lineReceived(self, line):
        if self.mode is DATA:
            return self.handleDataLine(line)
        command = string.split(line, None, 1)[0]
        method = getattr(self, 'do_'+string.upper(command), None)
        if method is None:
            method = self.do_UNKNOWN
        else:
            line = line[len(command):]
        return method(string.strip(line))

    def do_UNKNOWN(self, rest):
        self.sendCode(502, 'Command not implemented')

    def do_HELO(self, rest):
        self.__helo = rest
        self.sendCode(250, 'Nice to meet you')

    def do_QUIT(self, rest):
        self.sendCode(221, 'See you later')
        self.transport.loseConnection()

    def do_MAIL(self, rest):
        from_ = rest[len("MAIL:<"):-len(">")]
        self.validateFrom(self.__helo, from_, self._fromValid,
                                              self._fromInvalid)

    def _fromValid(self, from_):
        self.__from = from_
        self.sendCode(250, 'From address accepted')

    def _fromInvalid(self, from_):
        self.sendCode(550, 'No mail for you!')

    def do_RCPT(self, rest):
        to = rest[len("TO:<"):-len(">")]
        user = User(to, self.__helo, self, self.__from)
        self.validateTo(user, self._toValid, self._toInvalid)

    def _toValid(self, to):
        self.__to = self.__to + (to,)
        self.sendCode(250, 'Address recognized')

    def _toInvalid(self, to):
        self.sendCode(550, 'Cannot receive for specified address')

    def do_DATA(self, rest):
        if self.__from is None or not self.__to:  
            self.sendCode(550, 'Must have valid receiver and originator')
            return
        self.__buffer = []
        self.mode = DATA
        self.sendCode(354, 'Continue')

    def do_RSET(self, rest):
        self.__init__()
        self.sendCode(250, 'I remember nothing.')

    def handleDataLine(self, line):
        if line[:1] == '.':
            if line == '.':
                self.mode = COMMAND
                helo, origin, recipients = self.__helo, self.__from, self.__to
                message = string.join(self.__buffer, '\n')+'\n'
                self.__from = None
                self.__to = ()
                del self.__buffer
                success = self._messageHandled
                failure = self._messageNotHandled
                self.handleMessage(recipients, message, success, failure)
                return
            line = line[1:]
        self.__buffer.append(line)

    def _messageHandled(self):
        self.sendCode(250, 'Delivery in progress')

    def _messageNotHandled(self):
        self.sendCode(550, 'Could not send e-mail')

    # overridable methods:
    def validateFrom(self, helo, origin, success, failure):
        success(origin)

    def validateTo(self, user, success, failure):
        success(user)

    def handleMessage(self, recipients, message, 
                      success, failure):
        success()


class DomainSMTP(SMTP):

    def validateTo(self, user, success, failure):
        if not self.factory.domains.has_key(user.domain):
            failure(user)
            return
        self.factory.domains[user.domain].exists(user, success, failure)

    def handleMessage(self, users, message, success, failure):
        for user in users:
            self.factory.domains[user.domain].saveMessage(user, message)
        success()


class SMTPClient(basic.LineReceiver):

    def __init__(self, identity):
        self.identity = identity

    def connectionMade(self):
        self.state = 'helo'

    def lineReceived(self, line):
        if len(line)<4 or (line[3] not in ' -'):
            raise ValueError("invalid line from SMTP server %s" % line)
        if line[3] == '-':
            return
        code = int(line[:3])
        method =  getattr(self, 'smtpCode_%d_%s' % (code, self.state), 
                                self.smtpCode_default)
        method(line[4:])

    def smtpCode_220_helo(self, line):
        self.sendLine('HELO '+self.identity)
        self.state = 'from'

    def smtpCode_250_from(self, line):
        from_ = self.getMailFrom()
        if from_ is not None:
            self.sendLine('MAIL FROM:<%s>' % from_)
            self.state = 'afterFrom'
        else:
            self.sendLine('QUIT')
            self.state = 'quit'

    def smtpCode_250_afterFrom(self, line):
        self.toAddresses = self.getMailTo()
        self.successAddresses = []
        self.state = 'to'
        self.sendToOrData()

    def smtpCode_221_quit(self, line):
        self.transport.loseConnection()

    def smtpCode_default(self, line):
        self.transport.loseConnection()

    def sendToOrData(self):
        if not self.toAddresses:
            if self.successAddresses:
                self.sendLine('DATA')
                self.state = 'data'
            else:
                self.sentMail([])
                self.smtpCode_250_from('')
        else:
            self.lastAddress = self.toAddresses.pop()
            self.sendLine('RCPT TO:<%s>' % self.lastAddress)

    def smtpCode_250_to(self, line):
        self.successAddresses.append(self.lastAddress)
        self.sendToOrData()

    def smtpCode_354_data(self, line):
        for line in string.split(self.getMailData(), '\n')[:-1]:
            if line[:1] == '.':
                line = line+'.'
            self.sendLine(line)
        self.sendLine('.')
        self.state = 'afterData'

    def smtpCode_250_afterData(self, line):
        self.sentMail(self.successAddresses)
        self.smtpCode_250_from('')
