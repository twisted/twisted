# -*- test-case-name: twisted.test.test_mail -*-
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
from twisted.protocols import pop3
from twisted.protocols import smtp
from twisted.internet import protocol
from twisted.internet import defer
from twisted.copyright import longversion
from twisted.python import log

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials

class DomainMixin:
    """A server that uses twisted.mail service's domains."""
    
    service = None
    protocolName = None
    domainMixinBase = None

    def receivedHeader(self, helo, origin, recipients):
        from_ = "from %s ([%s])" % (helo[0], helo[1])
        by = "by %s with %s (%s)" % (
            self.host, self.protocolName, longversion
        )
        for_ = "for %s; %s" % (' '.join(map(str, recipients)), smtp.rfc822date())
        return "Received: %s\n\t%s\n\t%s" % (from_, by, for_)
    
    def validateTo(self, user):
        return defer.maybeDeferred(
            self.service.domains[user.dest.domain].exists,
            user
        ).addCallback(lambda result: user)

    def validateFrom(self, helo, origin):
        if not helo:
            raise smtp.SMTPBadSender(origin, 503, "Who are you?  Say HELO first.")
        return origin

    def startMessage(self, users):
        ret = []
        for user in users:
            ret.append(self.service.domains[user.dest.domain].startMessage(user))
        return ret

    def connectionLost(self, reason):
        log.msg('Disconnected from %s' % (self.transport.getPeer()[1:],))
        self.domainMixinBase.connectionLost(self, reason)

class DomainSMTP(DomainMixin, smtp.SMTP):
    protocolName = 'smtp'
    domainMixinBase = smtp.SMTP

class DomainESMTP(DomainMixin, smtp.ESMTP):
    protocolName = 'esmtp'
    domainMixinBase = smtp.ESMTP

class SMTPFactory(smtp.SMTPFactory):
    """A protocol factory for SMTP."""

    protocol = DomainSMTP

    def __init__(self, service):
        smtp.SMTPFactory.__init__(self)
        self.service = service
    
    def buildProtocol(self, addr):
        log.msg('Connection from %s' % (addr,))
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.service = self.service
        return p

class ESMTPFactory(SMTPFactory):
    protocol = DomainESMTP
    
class VirtualPOP3(pop3.POP3):
    """Virtual hosting POP3."""

    service = None

    domainSpecifier = '@' # Gaagh! I hate POP3. No standardized way
                          # to indicate user@host. '@' doesn't work
                          # with NS, e.g.

    def authenticateUserAPOP(self, user, digest):
        # Override the default lookup scheme to allow virtual domains
        user, domain = self.lookupDomain(user)
        try:
            portal = self.service.lookupPortal(domain)
        except KeyError:
            return defer.fail(cred.error.UnauthorizedLogin())
        else:
            return portal.login(
                pop3.APOPCredentials(self.magic, user, digest),
                None,
                pop3.IMailbox
            )

    def authenticateUserPASS(self, user, password):
        portal = self.service.defaultPortal()
        return portal.login(
            cred.credentials.UsernamePassword(user, password),
            None,
            pop3.IMailbox
        )

    def lookupDomain(self, user):
        try:
            user, domain = user.split(self.domainSpecifier, 1)
        except ValueError:
            domain = ''
        if domain not in self.service.domains:
             raise pop3.POP3Error("no such domain %s" % domain)
        return user, domain


class POP3Factory(protocol.ServerFactory):
    """POP3 protocol factory."""

    protocol = VirtualPOP3
    service = None

    def __init__(self, service):
        self.service = service
    
    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)
        p.service = self.service
        return p

#
# It is useful to know, perhaps, that the required file for this to work can
# be created thusly:
#
# openssl req -x509 -newkey rsa:2048 -keyout file.key -out file.crt \
# -days 365 -nodes
#
# And then cat file.key and file.crt together.  The number of days and bits
# can be changed, of course.
#
class SSLContextFactory:
    """An SSL Context Factory
    
    This loads a certificate and private key from a specified file.
    """
    def __init__(self, filename):
        self.filename = filename

    def getContext(self):
        """Create an SSL context."""
        from OpenSSL import SSL
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_certificate_file(self.filename)
        ctx.use_privatekey_file(self.filename)
        return ctx
