"""Mail support for twisted python.
"""

from twisted.protocols import protocol

def createDomainsFactory(protocol_handler, domains):
    ret = protocol.Factory()
    ret.protocol = protocol_handler
    ret.domains = domains
    return ret

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
