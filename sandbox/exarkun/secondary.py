# -*- coding: Latin-1 -*-

from twisted.names import common
from twisted.names import client

from twisted.application import service

class SecondaryAuthority(service.Service):
    refreshCall = None
    
    def __init__(self, primary, domains):
        """
        @param primary: The IP address of the server from which to perform
        zone transfers.
        
        @param domains: A sequence of domain names for which to perform
        zone transfers.
        """
        self.primary = primary
        self.domains = domains
    
    def startService(self):
        service.Service.startService(self)
        self._refreshDomains()
    
    def stopService(self):
        service.Service.stopService(self)
        if self.refreshCall is not None:
            self.refreshCall.cancel()
            del self.refreshCall
    
    def _refreshDomains(self):
        for d in self.domains:
            

class SecondaryAuthority(common.ResolverBase):
    """An Authority that keeps itself updated by performing zone transfers"""
    
    transferring = False
    
    def __init__(self, primaryIP, domain):
        self.primary = primary
        self.domain = domain
    
    def transfer(self):
        if self.transferring:
            return
        self.transfering = True

        return client.Resolver(servers=[(address, dns.PORT)]
            ).lookupZone(self.domain
            ).addCallback(self._cbZone
            ).addErrback(self._ebZone
            )
    
    def _cbZone(self, zone):
        self.records = {self.domain: zone}
    
    def _ebZone(self, failure):
        log.msg("Updating %s from %s failed during zone transfer" % (self.domain, self.primary))
        log.err(failure)
    
    def updateLoop(self):
        self.transfer().addCallbacks(self._cbTransferred, self._ebTransferred)
    
    def _cbTransferred(self):
        self.call = reactor.callLater(
