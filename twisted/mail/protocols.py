# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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

"""Protocol support for twisted.mail."""

# twisted imports
from twisted.protocols import pop3, smtp
from twisted.internet import protocol

# system imports
import string


class DomainSMTP(smtp.SMTP):
    """SMTP server that uses twisted.mail service's domains."""
    
    def validateTo(self, user, success, failure):
        if not self.service.domains.has_key(user.domain):
            failure(user)
            return
        self.service.domains[user.domain].exists(user, success, failure)

    def startMessage(self, users):
        ret = []
        for user in users:
            ret.append(self.service.domains[user.domain].startMessage(user))
        return ret


class SMTPFactory(protocol.ServerFactory):
    """A protocol factory for SMTP."""
    
    def __init__(self, service):
        self.service = service
    
    def buildProtocol(self, addr):
        p = DomainSMTP()
        p.service = self.service
        return p


class VirtualPOP3(pop3.POP3):
    """Virtual hosting POP3."""

    domainSpecifier = '@' # Gaagh! I hate POP3. No standardized way
                          # to indicate user@host. '@' doesn't work
                          # with NS, e.g.

    def authenticateUserAPOP(self, user, digest):
        try:
            user, domain = string.split(user, self.domainSpecifier, 1)
        except ValueError:
            domain = ''
        if not self.service.domains.has_key(domain):
             raise pop3.POP3Error("no such domain %s" % domain)
        domain = self.service.domains[domain]
        mbox = domain.authenticateUserAPOP(user, self.magic, digest, domain)
        if mbox is None:
            raise pop3.POP3Error("bad authentication")
        return mbox


class POP3Factory(protocol.ServerFactory):
    """POP3 protocol factory."""

    def __init__(self, service):
        self.service = service
    
    def buildProtocol(self, addr):
        p = VirtualPOP3()
        p.service = self.service
        return p


class SMTPClientFactory(protocol.ClientFactory):
    """
    Factory to manage the connections required to send an email.
    """

    protocol = smtp.SMTPSender
    
    def __init__(self, fromEmail, toEmail, file, deferred):
        self.fromEmail = fromEmail
        self.toEmail = toEmail
        self.file = file
        self.result = deferred
        self.sendFinished = 0
    
    def clientConnectionFailed(self, connector, error):
        self.result.errback(error)

    def clientConnectionLost(self, connector, error):
        # if email wasn't sent, try again
        if not self.sendFinished:
            connector.connect() # reconnect to SMTP server

    def buildProtocol(self, addr):
        p = self.protocol(self.fromEmail)
        p.factory = self
        return p
