# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Protocol support for twisted.mail."""

# twisted imports
from twisted.mail import pop3
from twisted.mail import smtp
from twisted.internet import protocol
from twisted.internet import defer
from twisted.copyright import longversion
from twisted.python import log

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials

from twisted.mail import relay

from zope.interface import implements


class DomainDeliveryBase:
    """A server that uses twisted.mail service's domains."""

    implements(smtp.IMessageDelivery)
    
    service = None
    protocolName = None

    def __init__(self, service, user, host=smtp.DNSNAME):
        self.service = service
        self.user = user
        self.host = host
    
    def receivedHeader(self, helo, origin, recipients):
        authStr = heloStr = ""
        if self.user:
            authStr = " auth=%s" % (self.user.encode('xtext'),)
        if helo[0]:
            heloStr = " helo=%s" % (helo[0],)
        from_ = "from %s ([%s]%s%s)" % (helo[0], helo[1], heloStr, authStr)
        by = "by %s with %s (%s)" % (
            self.host, self.protocolName, longversion
        )
        for_ = "for <%s>; %s" % (' '.join(map(str, recipients)), smtp.rfc822date())
        return "Received: %s\n\t%s\n\t%s" % (from_, by, for_)
    
    def validateTo(self, user):
        # XXX - Yick.  This needs cleaning up.
        if self.user and self.service.queue:
            d = self.service.domains.get(user.dest.domain, None)
            if d is None:
                d = relay.DomainQueuer(self.service, True)
        else:
            d = self.service.domains[user.dest.domain]
        return defer.maybeDeferred(d.exists, user)

    def validateFrom(self, helo, origin):
        if not helo:
            raise smtp.SMTPBadSender(origin, 503, "Who are you?  Say HELO first.")
        if origin.local != '' and origin.domain == '':
            raise smtp.SMTPBadSender(origin, 501, "Sender address must contain domain.")
        return origin

    def startMessage(self, users):
        ret = []
        for user in users:
            ret.append(self.service.domains[user.dest.domain].startMessage(user))
        return ret


class SMTPDomainDelivery(DomainDeliveryBase):
    protocolName = 'smtp'

class ESMTPDomainDelivery(DomainDeliveryBase):
    protocolName = 'esmtp'

class DomainSMTP(SMTPDomainDelivery, smtp.SMTP):
    service = user = None

    def __init__(self, *args, **kw):
        import warnings
        warnings.warn(
            "DomainSMTP is deprecated.  Use IMessageDelivery objects instead.",
            DeprecationWarning, stacklevel=2,
        )
        smtp.SMTP.__init__(self, *args, **kw)
        if self.delivery is None:
            self.delivery = self

class DomainESMTP(ESMTPDomainDelivery, smtp.ESMTP):
    service = user = None

    def __init__(self, *args, **kw):
        import warnings
        warnings.warn(
            "DomainESMTP is deprecated.  Use IMessageDelivery objects instead.",
            DeprecationWarning, stacklevel=2,
        )
        smtp.ESMTP.__init__(self, *args, **kw)
        if self.delivery is None:
            self.delivery = self

class SMTPFactory(smtp.SMTPFactory):
    """A protocol factory for SMTP."""

    protocol = smtp.SMTP
    portal = None

    def __init__(self, service, portal = None):
        smtp.SMTPFactory.__init__(self)
        self.service = service
        self.portal = portal
    
    def buildProtocol(self, addr):
        log.msg('Connection from %s' % (addr,))
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.service = self.service
        p.portal = self.portal
        return p

class ESMTPFactory(SMTPFactory):
    protocol = smtp.ESMTP
    context = None

    def __init__(self, *args):
        SMTPFactory.__init__(self, *args)
        self.challengers = {
            'CRAM-MD5': cred.credentials.CramMD5Credentials
        }
    
    def buildProtocol(self, addr):
        p = SMTPFactory.buildProtocol(self, addr)
        p.challengers = self.challengers
        p.ctx = self.context
        return p

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
        user, domain = self.lookupDomain(user)
        try:
            portal = self.service.lookupPortal(domain)
        except KeyError:
            return defer.fail(cred.error.UnauthorizedLogin())
        else:
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
