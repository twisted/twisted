from twisted.python import components

class IService(components.Interface):

    def setParent(self, parent):
        pass

    def startService(self):
        pass

    def stopService(self):
        pass

    def preStartService(self):
        pass


class Service:

    __implements__ = IService,

    running = 0
    name = None
    parent = None

    def __getstate__(self):
        dict = self.__dict__
        if dict.has_key("running"):
            del dict['running']
        return dict

    def setName(self, name):
        if self.parent is not None:
            raise RuntimeError("cannot change name when parent exists")
        self.name = name

    def setParent(self, parent):
        if self.parent is not None:
            self.unsetParent()
        self.parent = parent
        self.parent.addService(self)

    def unsetParent(self):
        self.parent.removeService(self)
        self.parent = None

    def preStartService(self):
        pass

    def startService(self):
        self.running = 1

    def stopService(self):
        self.running = 1


class MultiService(Service):

    def __init__(self):
        self.services = []
        self.namedServices = {}
        self.parent = None

    def preStartService(self):
        Service.preStartService(self)
        for service in self:
            service.preStartService()

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

    def __iter__(self):
        return iter(self.services)

    def addService(self, service):
        if service.name is not None:
            self.namedServices[service.name] = service
        self.services.append(service)

    def removeService(self, service):
        if service.name:
            del self.namedServices[service.name]
        self.services.remove(service)
