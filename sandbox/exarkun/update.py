# -*- coding: Latin-1 -*-

from twisted.internet import defer
from twisted.python import components
from twisted.python import failure
from twisted.spread import pb

class IWriteableZone(components.Interface):
    def setRecord(self, name, record, owner=None):
        """Add a record to this zone.
        
        @type name: C{str}
        @param name: The name of the domain for which to add a record.
        
        @type record: Any object implementing C{twisted.protocols.dns.IRecord}
        @param record: The record to associate with this domain.
        
        @type owner: C{str}
        @param owner: The user to indicate owns this record (and thus will be
        allowed to remove it later).
        """
    
    def removeRecords(self, name):
        """Remove records for the given domain.
        
        @type name: C{str}
        @param name: The domain for which to remove records.
        """

class IReadableZone(components.Interface):
    def getRecords(self, name):
        """Retrieve all records for a given domain.

        @type name: C{str}
        @param name: The domain for which to retrieve records.
        
        @rtype: C{list} of objects implementing C{IRecord} or C{None}
        """


class IMappingZone(components.Interface):
    """
    A zone which consists of a map of domain names to record information.
    
    @type records: mapping
    @ivar records: An object mapping lower-cased domain names to lists of
    L{twisted.protocols.dns.IRecord} objects.
    """

class UpdateableAuthority:
    """A wrapper around IMappingZone authorities that allows modifications.
    """

    __implements__ = (IWriteableZone, IReadableZone)
    
    def __init__(self, authority):
        """
        @type authority: An object implementing C{IMappingZone}
        @param authority: The authority for which we will provide
        updates.
        """
        self.authority = authority

    def setRecord(self, name, record):
        self.authority.records.setdefault(name, []).append(record)
    
    def removeRecords(self, name):
        try:
            del self.authority.records[name]
        except KeyError:
            pass
    
    def getRecords(self, name):
        return self.authority.records.get(name)

class IUser(components.Interface):
    """
    @cvar name: This user's name.
    """
    
    def __init__(self, control, name):
        pass
    
ACCESS_DENIED = failure.Failure(Exception("DENIED"))
    
class User(pb.Perspective):
    __implements__ = (IUser,)
    
    def __init__(self, name, authority, domains=()):
        self.name = name
        self.auth = authority
        self.domains = dict([(d.lower(), None) for d in domains])
    
    def addDomain(self, name):
        self.domains[name.lower()] = None
    
    def removeDomain(self, name):
        del self.domains[name.lower()]

    def getDomains(self):
        return self.domains.keys()

    def remote_setRecord(self, name, record):
        if name.lower() in self.domains:
            return self.auth.setRecord(name, record)
        return ACCESS_DENIED
    
    def remote_removeRecords(self, name):
        if name.lower() in self.domains:
            return self.auth.removeRecords(name)
        return ACCESS_DENIED
    
    def remote_getRecords(self, name):
        if name.lower() in self.domains:
            return self.auth.getRecords(name)
        return ACCESS_DENIED
