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
from twisted.python import components
from twisted.internet import defer
from twisted.persisted import sob

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
            self.disownServiceParent()
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
        self.running = 0


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
        l = []
        for service in self:
            l.append(defer.maybeDeferred(service.stopService))
        return defer.DeferredList(l)

    def getService(self, idx):
        return self.services[idx]

    def getServiceNamed(self, name):
        return self.namedServices[name]

    def __iter__(self):
        return iter(self.services)

    def addService(self, service):
        if service.name is not None:
            if self.namedServices.has_key(service.name):
                raise RuntimeError("cannot have two services with same name")
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


class IProcess(components.Interface):
    pass


class Process:

    __implements__ = IProcess,

    processName = None

    def __init__(self, uid=None, gid=None):
        self.uid = uid or 0
        self.gid = gid or 0
    

def Application(name, uid=None, gid=None):
    ret = components.Componentized()
    service = MultiService()
    service.setName(name)
    ret.addComponent(service, ignoreClass=1)
    ret.addComponent(sob.Persistant(ret, name), ignoreClass=1)
    ret.addComponent(Process(uid, gid), ignoreClass=1)
    return ret
