"""Mail support for twisted python.
"""

from twisted.protocols import smtp, pop3, protocol

class DomainBasedFactory(protocol.Factory):
    """A server for multiple mail domains.
    """
    def __init__(self, domains):
        self.domains = domains


class VirtualSMTPFactory(DomainBasedFactory):
    """A virtual SMTP server.
    """
    def buildProtocol(self, addr):
        p = smtp.DomainSMTPHandler()
        p.factory = self
        return p


class VirtualPOP3Factory(DomainBasedFactory):
    """A virtual POP3 server.
    """
    def buildProtocol(self, addr):
        p = pop3.VirtualPOP3()
        p.factory = self
        return p


class DomainWithDefaultDict:

    def __init__(self, domains, default):
        self.domains = domains
        self.default = default

    def has_key(self, name):
        return 1

    def __getitem__(self, name):
        return self.domains.get(name, self.default)


class BounceDomain:
    """ UNDOCUMENTED
    """
    def exists(self, name, domain):
        """ UNDOCUMENTED
        """
        return 0
