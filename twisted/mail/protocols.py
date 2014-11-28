# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Mail protocol support.
"""

from twisted.mail import pop3
from twisted.mail import smtp
from twisted.internet import protocol
from twisted.internet import defer
from twisted.copyright import longversion
from twisted.python import log
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials

from twisted.mail import relay

from zope.interface import implements



class DomainDeliveryBase:
    """
    A base class for message delivery using the domains of a mail service.

    @ivar service: See L{__init__}
    @ivar user: See L{__init__}
    @ivar host: See L{__init__}

    @type protocolName: L{bytes}
    @ivar protocolName: The protocol being used to deliver the mail.
        Sub-classes should set this appropriately.
    """
    implements(smtp.IMessageDelivery)

    service = None
    protocolName = None

    def __init__(self, service, user, host=smtp.DNSNAME):
        """
        @type service: L{MailService}
        @param service: A mail service.

        @type user: L{bytes} or L{NoneType <types.NoneType>}
        @param user: The authenticated SMTP user.

        @type host: L{bytes}
        @param host: The hostname.
        """
        self.service = service
        self.user = user
        self.host = host


    def receivedHeader(self, helo, origin, recipients):
        """
        Generate a received header string for a message.

        @type helo: 2-L{tuple} of (L{bytes}, L{bytes})
        @param helo: The client's identity as sent in the HELO command and its
            IP address.

        @type origin: L{Address}
        @param origin: The origination address of the message.

        @type recipients: L{list} of L{User}
        @param recipients: The destination addresses for the message.

        @rtype: L{bytes}
        @return: A received header string.
        """
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
        """
        Validate the address for which a message is destined.

        @type user: L{User}
        @param user: The destination address.

        @rtype: L{Deferred <defer.Deferred>} which successfully fires with
            no-argument callable which returns L{IMessage <smtp.IMessage>}
            provider.
        @return: A deferred which successfully fires with a no-argument
            callable which returns a message receiver for the destination.

        @raise SMTPBadRcpt: When messages cannot be accepted for the
            destination address.
        """
        # XXX - Yick.  This needs cleaning up.
        if self.user and self.service.queue:
            d = self.service.domains.get(user.dest.domain, None)
            if d is None:
                d = relay.DomainQueuer(self.service, True)
        else:
            d = self.service.domains[user.dest.domain]
        return defer.maybeDeferred(d.exists, user)


    def validateFrom(self, helo, origin):
        """
        Validate the address from which a message originates.

        @type helo: 2-L{tuple} of (L{bytes}, L{bytes})
        @param helo: The client's identity as sent in the HELO command and its
            IP address.

        @type origin: L{Address}
        @param origin: The origination address of the message.

        @rtype: L{Address}
        @return: The origination address.

        @raise SMTPBadSender: When messages cannot be accepted from the
            origination address.
        """
        if not helo:
            raise smtp.SMTPBadSender(origin, 503, "Who are you?  Say HELO first.")
        if origin.local != '' and origin.domain == '':
            raise smtp.SMTPBadSender(origin, 501, "Sender address must contain domain.")
        return origin



class SMTPDomainDelivery(DomainDeliveryBase):
    """
    A domain delivery base class for use in an SMTP server.
    """
    protocolName = 'smtp'



class ESMTPDomainDelivery(DomainDeliveryBase):
    """
    A domain delivery base class for use in an ESMTP server.
    """
    protocolName = 'esmtp'



class DomainSMTP(SMTPDomainDelivery, smtp.SMTP):
    """
    An SMTP server which uses the domains of a mail service.
    """
    service = user = None

    def __init__(self, *args, **kw):
        """
        Initialize the SMTP server.

        @type args: 2-L{tuple} of (L{IMessageDelivery} provider or
            L{NoneType <types.NoneType>}, L{IMessageDeliveryFactory}
            provider or L{NoneType <types.NoneType>})
        @param args: Positional arguments for L{SMTP.__init__}

        @type kw: L{dict}
        @param kw: Keyword arguments for L{SMTP.__init__}.
        """
        import warnings
        warnings.warn(
            "DomainSMTP is deprecated.  Use IMessageDelivery objects instead.",
            DeprecationWarning, stacklevel=2,
        )
        smtp.SMTP.__init__(self, *args, **kw)
        if self.delivery is None:
            self.delivery = self



class DomainESMTP(ESMTPDomainDelivery, smtp.ESMTP):
    """
    An ESMTP server which uses the domains of a mail service.
    """
    service = user = None

    def __init__(self, *args, **kw):
        """
        Initialize the ESMTP server.

        @type args: 2-L{tuple} of (L{IMessageDelivery} provider or
            L{NoneType <types.NoneType>}, L{IMessageDeliveryFactory}
            provider or L{NoneType <types.NoneType>})
        @param args: Positional arguments for L{ESMTP.__init__}

        @type kw: L{dict}
        @param kw: Keyword arguments for L{ESMTP.__init__}.
        """
        import warnings
        warnings.warn(
            "DomainESMTP is deprecated.  Use IMessageDelivery objects instead.",
            DeprecationWarning, stacklevel=2,
        )
        smtp.ESMTP.__init__(self, *args, **kw)
        if self.delivery is None:
            self.delivery = self



class SMTPFactory(smtp.SMTPFactory):
    """
    An SMTP server protocol factory.

    @ivar service: See L{__init__}
    @ivar portal: See L{__init__}

    @type protocol: no-argument callable which returns a L{Protocol
        <protocol.Protocol>} subclass
    @ivar protocol: A callable which creates a protocol.  The default value is
        L{SMTP}.
    """
    protocol = smtp.SMTP
    portal = None

    def __init__(self, service, portal = None):
        """
        @type service: L{MailService}
        @param service: An email service.

        @type portal: L{Portal <twisted.cred.portal.Portal>} or
            L{NoneType <types.NoneType>}
        @param portal: A portal to use for authentication.
        """
        smtp.SMTPFactory.__init__(self)
        self.service = service
        self.portal = portal


    def buildProtocol(self, addr):
        """
        Create an instance of an SMTP server protocol.

        @type addr: L{IAddress <twisted.internet.interfaces.IAddress>} provider
        @param addr: The address of the SMTP client.

        @rtype: L{SMTP}
        @return: An SMTP protocol.
        """
        log.msg('Connection from %s' % (addr,))
        p = smtp.SMTPFactory.buildProtocol(self, addr)
        p.service = self.service
        p.portal = self.portal
        return p



class ESMTPFactory(SMTPFactory):
    """
    An ESMTP server protocol factory.

    @type protocol: no-argument callable which returns a L{Protocol
        <protocol.Protocol>} subclass
    @ivar protocol: A callable which creates a protocol.  The default value is
        L{ESMTP}.

    @type context: L{ContextFactory <twisted.internet.ssl.ContextFactory>} or
        L{NoneType <types.NoneType>}
    @ivar context: A factory to generate contexts to be used in negotiating
        encrypted communication.

    @type challengers: L{dict} mapping L{bytes} to no-argument callable which
        returns L{ICredentials <twisted.cred.credentials.ICredentials>}
        subclass provider.
    @ivar challengers: A mapping of acceptable authorization mechanism to
        callable which creates credentials to use for authentication.
    """
    protocol = smtp.ESMTP
    context = None

    def __init__(self, *args):
        """
        @param args: Arguments for L{SMTPFactory.__init__}

        @see: L{SMTPFactory.__init__}
        """
        SMTPFactory.__init__(self, *args)
        self.challengers = {
            'CRAM-MD5': cred.credentials.CramMD5Credentials
        }


    def buildProtocol(self, addr):
        """
        Create an instance of an ESMTP server protocol.

        @type addr: L{IAddress <twisted.internet.interfaces.IAddress>} provider
        @param addr: The address of the ESMTP client.

        @rtype: L{ESMTP}
        @return: An ESMTP protocol.
        """
        p = SMTPFactory.buildProtocol(self, addr)
        p.challengers = self.challengers
        p.ctx = self.context
        return p



class VirtualPOP3(pop3.POP3):
    """
    A virtual hosting POP3 server.

    @type service: L{MailService}
    @ivar service: The email service that created this server.  This must be
        set by the service.

    @type domainSpecifier: L{bytes}
    @ivar domainSpecifier: The character to use to split an email address into
        local-part and domain. The default is '@'.
    """
    service = None

    domainSpecifier = '@' # Gaagh! I hate POP3. No standardized way
                          # to indicate user@host. '@' doesn't work
                          # with NS, e.g.

    def authenticateUserAPOP(self, user, digest):
        """
        Perform APOP authentication.

        Override the default lookup scheme to allow virtual domains.

        @type user: L{bytes}
        @param user: The name of the user attempting to log in.

        @type digest: L{bytes}
        @param digest: The challenge response.

        @rtype: L{Deferred} which successfully results in 3-L{tuple} of
            (L{IMailbox <pop3.IMailbox>}, L{IMailbox <pop3.IMailbox>}
            provider, no-argument callable)
        @return: A deferred which fires when authentication is complete.
            If successful, it returns an L{IMailbox <pop3.IMailbox>} interface,
            a mailbox and a logout function. If authentication fails, the
            deferred fails with an L{UnauthorizedLogin
            <twisted.cred.error.UnauthorizedLogin>} error.
        """
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
        """
        Perform authentication for a username/password login.

        Override the default lookup scheme to allow virtual domains.

        @type user: L{bytes}
        @param user: The name of the user attempting to log in.

        @type password: L{bytes}
        @param password: The password to authenticate with.

        @rtype: L{Deferred} which successfully results in 3-L{tuple} of
            (L{IMailbox <pop3.IMailbox>}, L{IMailbox <pop3.IMailbox>}
            provider, no-argument callable)
        @return: A deferred which fires when authentication is complete.
            If successful, it returns an L{IMailbox <pop3.IMailbox>} interface,
            a mailbox and a logout function. If authentication fails, the
            deferred fails with an L{UnauthorizedLogin
            <twisted.cred.error.UnauthorizedLogin>} error.
        """
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
        """
        Check whether a domain is among the virtual domains supported by the
        mail service.

        @type user: L{bytes}
        @param user: An email address.

        @rtype: 2-L{tuple} of (L{bytes}, L{bytes})
        @return: The local part and the domain part of the email address if the
            domain is supported.

        @raise POP3Error: When the domain is not supported by the mail service.
        """
        try:
            user, domain = user.split(self.domainSpecifier, 1)
        except ValueError:
            domain = ''
        if domain not in self.service.domains:
             raise pop3.POP3Error("no such domain %s" % domain)
        return user, domain



class POP3Factory(protocol.ServerFactory):
    """
    A POP3 server protocol factory.

    @ivar service: See L{__init__}

    @type protocol: no-argument callable which returns a L{Protocol
        <protocol.Protocol>} subclass
    @ivar protocol: A callable which creates a protocol.  The default value is
        L{VirtualPOP3}.
    """
    protocol = VirtualPOP3
    service = None

    def __init__(self, service):
        """
        @type service: L{MailService}
        @param service: An email service.
        """
        self.service = service


    def buildProtocol(self, addr):
        """
        Create an instance of a POP3 server protocol.

        @type addr: L{IAddress <twisted.internet.interfaces.IAddress>} provider
        @param addr: The address of the POP3 client.

        @rtype: L{POP3}
        @return: A POP3 protocol.
        """
        p = protocol.ServerFactory.buildProtocol(self, addr)
        p.service = self.service
        return p



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
    """
    An SSL context factory.

    @ivar filename: See L{__init__}
    """
    deprecatedModuleAttribute(
        Version("Twisted", 12, 2, 0),
        "Use twisted.internet.ssl.DefaultOpenSSLContextFactory instead.",
        "twisted.mail.protocols", "SSLContextFactory")

    def __init__(self, filename):
        """
        @type filename: L{bytes}
        @param filename: The name of a file containing a certificate and
            private key.
        """
        self.filename = filename


    def getContext(self):
        """
        Create an SSL context.

        @rtype: C{OpenSSL.SSL.Context}
        @return: An SSL context configured with the certificate and private key
            from the file.
        """
        from OpenSSL import SSL
        ctx = SSL.Context(SSL.SSLv23_METHOD)
        ctx.use_certificate_file(self.filename)
        ctx.use_privatekey_file(self.filename)
        return ctx
