# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
from twisted.python import components, runtime
from twisted.persisted import sob
import os

class IService(components.Interface):

    def setName(self, name):
        pass

    def setServiceParent(self, parent):
        pass

    def disownServiceParent(self):
        pass

    def startService(self):
        pass

    def stopService(self):
        pass

    def privilegedStartService(self):
        pass


class Service:

    __implements__ = IService,

    running = 0
    name = None
    parent = None

    def __getstate__(self):
        dict = self.__dict__.copy()
        if dict.has_key("running"):
            del dict['running']
        return dict

    def setName(self, name):
        if self.parent is not None:
            raise RuntimeError("cannot change name when parent exists")
        self.name = name

    def setServiceParent(self, parent):
        if self.parent is not None:
            self.unsetParent()
        self.parent = parent
        self.parent.addService(self)

    def disownServiceParent(self):
        self.parent.removeService(self)
        self.parent = None

    def privilegedStartService(self):
        pass

    def startService(self):
        self.running = 1

    def stopService(self):
        self.running = 1


class IServiceCollection(components.Interface):

    def getService(self, idx):
        pass

    def getServiceNamed(self, name):
        pass

    def __iter__(self):
        pass

    def addService(self, service):
        pass

    def removeService(self, service):
        pass


class MultiService(Service):

    __implements__ = Service.__implements__, IServiceCollection

    def __init__(self):
        self.services = []
        self.namedServices = {}
        self.parent = None

    def privilegedStartService(self):
        Service.privilegedStartService(self)
        for service in self:
            service.privilegedStartService()

    def startService(self):
        Service.startService(self)
        for service in self:
            service.startService()

    def stopService(self):
        Service.stopService(self)
        for service in self:
            service.stopService()

    def getService(self, idx):
        return self.services[idx]

    def getServiceNamed(self, name):
        return self.namedServices[name]

    def __iter__(self):
        return iter(self.services)

    def addService(self, service):
        if service.name is not None:
            self.namedServices[service.name] = service
        self.services.append(service)
        if self.running:
            service.startService()

    def removeService(self, service):
        if service.name:
            del self.namedServices[service.name]
        self.services.remove(service)
        if self.running:
            service.stopService()


class IProcess:
    pass


class Process:

    __implements__ = IProcess,

    processName = None

    def __init__(self, uid=None, gid=None):
            if uid is None:
                uid = os.getuid()
            self.uid = uid
            if gid is None:
                gid = os.getgid()
            self.gid = gid
    

def Application(name, uid=None, gid=None):
    ret = components.Componentized()
    service = MultiService()
    service.setName(name)
    ret.setComponent(IServiceCollection, service)
    ret.setComponent(IService, service)
    ret.setComponent(sob.IPersistable, sob.Persistant(ret, name))
    if runtime.platformType == "posix":
        ret.setComponent(IProcess, Process(uid, gid))
    return ret
