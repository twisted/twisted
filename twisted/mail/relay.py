
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

"""Support for relaying mail for twisted.mail"""

from twisted.protocols import smtp
from twisted.mail import mail

import os, time, cPickle


class DomainQueuer:
    """An SMTP domain which add messages to a queue."""

    def __init__(self, service):
        self.service = service

    def exists(self, user, success, failure):
        """Check whether we will relay

        Call overridable willRelay method
        """
        if self.willRelay(user.protocol):
            success(user)
        else:
            failure(user)

    def willRelay(self, protocol):
        """Check whether we agree to relay

        The default is to relay for non-inet connections or for
        localhost inet connections. Note that this means we are
        an open IPv6 relay
        """
        peer = protocol.transport.getPeer()
        return peer[0] != 'INET' or peer[1] == '127.0.0.1'

    def startMessage(self, user):
        """Add envelope to queue and returns ISMTPMessage."""
        queue = self.service.queue
        envelopeFile, smtpMessage = queue.createNewMessage()
        try:
            cPickle.dump([user.orig, '%s@%s' % (user.name, user.domain)], envelopeFile)
        finally:
            envelopeFile.close()
        return smtpMessage


class SMTPRelayer(smtp.SMTPClient):

    def __init__(self, messagePaths):
        self.messages = []
        self.names = []
        for message in messagePaths:
            fp = open(message+'-H')
            try:
                messageContents = cPickle.load(fp)
            finally:
                fp.close()
            fp = open(message+'-D')
            try:
                messageContents.append(fp.read())
            finally:
                fp.close()
            self.messages.append(messageContents)
            self.names.append(message)

    def getMailFrom(self):
        if not self.messages:
            return None
        return self.messages[0][0]

    def getMailTo(self):
        return [self.messages[0][1]]

    def getMailData(self):
        return self.messages[0][2]

    def sentMail(self, addresses):
        if addresses:
            os.remove(self.names[0]+'-D')
            os.remove(self.names[0]+'-H')
        del self.messages[0]
        del self.names[0]
