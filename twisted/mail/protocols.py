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

from twisted import cred
import twisted.cred.error
import twisted.cred.credentials

class DomainSMTP(smtp.SMTP):
    """SMTP server that uses twisted.mail service's domains."""
    
    service = None
    
    def validateTo(self, user):
        """Determine whether or not a given user exists.
        
        @return: True if the user exists, false otherwise.
        """
        if not self.service.domains.has_key(user.dest.domain):
            return defer.fail(smtp.SMTPBadRcpt(user))
        return self.service.domains[user.dest.domain].exists(user)

    def startMessage(self, users):
        ret = []
        for user in users:
            ret.append(self.service.domains[user.dest.domain].startMessage(user))
        return ret


class SMTPFactory(smtp.SMTPFactory):
    """A protocol factory for SMTP."""

    def __init__(self, service):
        self.service = service
    
    def buildProtocol(self, addr):
        p = DomainSMTP()
        p.service = self.service
        p.factory = self
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

    def __init__(self, service):
        self.service = service
    
    def buildProtocol(self, addr):
        p = VirtualPOP3()
        p.service = self.service
        p.factory = self
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
