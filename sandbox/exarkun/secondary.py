# -*- coding: Latin-1 -*-

from twisted.names import common
from twisted.names import client

class SecondaryAuthority(common.ResolverBase):
    """An Authority that keeps itself updated by performing zone transfers"""
    
    transferring = False
    
    def __init__(self, primary, domain):
        self.primary = primary
        self.domain = domain
    
    def transfer(self):
        if self.transferring:
            return
        self.transfering = True

        # Yea, this won't work
        client.getHostByName(self.primary
            ).addCallback(self._cbLookup
            ).addErrback(self._ebLookup
            ).addBoth(self._cbDoneTransfer
            )
    
    def _cbLookup(self, address):
        client.Resolver(servers=[(address, dns.PORT)]
            ).lookupZone(self.domain
            ).addCallback(self._cbZone
            ).addErrback(self._ebZone
            )
    
    def _ebLookup(self, failure):
        log.msg("Updating %s from %s failed during lookup" % (self.domain, self.primary))
        log.err(failure)

    def _cbZone(self, zone):
        self.records = {self.domain: zone}
    
    def _ebZone(self, failure):
        log.msg("Updating %s from %s failed during zone transfer" % (self.domain, self.primary))
        log.err(failure)
    
    def _cbDoneTransfer(self, _):
        self.transferring = False
