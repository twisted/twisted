# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.internet import task, defer
from twisted.names import dns
from twisted.names import common
from twisted.names import client
from twisted.names import resolve
from twisted.python import log, failure
from twisted.application import service

class SecondaryAuthorityService(service.Service):
    calls = None

    def __init__(self, primary, domains):
        """
        @param primary: The IP address of the server from which to perform
        zone transfers.

        @param domains: A sequence of domain names for which to perform
        zone transfers.
        """
        self.primary = primary
        self.domains = [SecondaryAuthority(primary, d) for d in domains]

    def getAuthority(self):
        return resolve.ResolverChain(self.domains)

    def startService(self):
        service.Service.startService(self)
        self.calls = [task.LoopingCall(d.transfer) for d in self.domains]
        i = 0
        from twisted.internet import reactor
        for c in self.calls:
            # XXX Add errbacks, respect proper timeouts
            reactor.callLater(i, c.start, 60 * 60)
            i += 1

    def stopService(self):
        service.Service.stopService(self)
        for c in self.calls:
            c.stop()


from twisted.names.authority import FileAuthority

class SecondaryAuthority(common.ResolverBase):
    """An Authority that keeps itself updated by performing zone transfers"""

    transferring = False

    soa = records = None
    def __init__(self, primaryIP, domain):
        common.ResolverBase.__init__(self)
        self.primary = primaryIP
        self.domain = domain

    def transfer(self):
        if self.transferring:
            return
        self.transfering = True
        return client.Resolver(servers=[(self.primary, dns.PORT)]
            ).lookupZone(self.domain
            ).addCallback(self._cbZone
            ).addErrback(self._ebZone
            )


    def _lookup(self, name, cls, type, timeout=None):
        if not self.soa or not self.records:
            return defer.fail(failure.Failure(dns.DomainError(name)))


        return FileAuthority.__dict__['_lookup'](self, name, cls, type, timeout)

    #shouldn't we just subclass? :P

    lookupZone = FileAuthority.__dict__['lookupZone']

    def _cbZone(self, zone):
        ans, _, _ = zone
        self.records = r = {}
        for rec in ans:
            if not self.soa and rec.type == dns.SOA:
                self.soa = (str(rec.name).lower(), rec.payload)
            else:
                r.setdefault(str(rec.name).lower(), []).append(rec.payload)

    def _ebZone(self, failure):
        log.msg("Updating %s from %s failed during zone transfer" % (self.domain, self.primary))
        log.err(failure)

    def update(self):
        self.transfer().addCallbacks(self._cbTransferred, self._ebTransferred)

    def _cbTransferred(self, result):
        self.transferring = False

    def _ebTransferred(self, failure):
        self.transferred = False
        log.msg("Transferring %s from %s failed after zone transfer" % (self.domain, self.primary))
        log.err(failure)
