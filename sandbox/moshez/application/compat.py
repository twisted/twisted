from twisted.python import components
from twisted.application import servers, clients

class IOldApplication(components.Interface):

    def listenWith(self, portType, *args, **kw):
        pass

    def unlistenWith(self, portType, *args, **kw):
        pass

    def listenTCP(self, port, factory, backlog=5, interface=''):
        pass

    def unlistenTCP(self, port, interface=''):
        pass

    def listenUNIX(self, filename, factory, backlog=5, mode=0666):
        pass

    def unlistenUNIX(self, filename):
        pass

    def listenUDP(self, port, proto, interface='', maxPacketSize=8192):
        pass

    def unlistenUDP(self, port, interface=''):
        pass

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        pass

    def unlistenSSL(self, port, interface=''):
        pass

    def connectWith(self, connectorType, *args, **kw):
        pass

    def connectUDP(self, remotehost, remoteport, protocol, localport=0,
                  interface='', maxPacketSize=8192):
        pass

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        pass

    def connectUNIX(self, address, factory, timeout=30):
        pass


class ServiceNetwork:

    __implements__ = IOldApplication,

    def __init__(self, app):
        self.app = app

    def listenWith(self, portType, *args, **kw):
        servers.GenericServer(portType, *args, **kw).setParent(self.app)

    def unlistenWith(self, portType, *args, **kw):
        raise NotImplementedError()

    def listenTCP(self, port, factory, backlog=5, interface=''):
        servers.TCPServer(port, factory, backlog, interface).setParent(self.app)
        pass

    def unlistenTCP(self, port, interface=''):
        raise NotImplementedError()

    def listenUNIX(self, filename, factory, backlog=5, mode=0666):
        servers.UNIXServer(filename, factory, backlog, mode).setParent(self.app)

    def unlistenUNIX(self, filename):
        raise NotImplementedError()

    def listenUDP(self, port, proto, interface='', maxPacketSize=8192):
        s = servers.UDPServer(port, proto, interface, maxPacketSize)
        s.setParent(self.app)

    def unlistenUDP(self, port, interface=''):
        raise NotImplementedError()

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        s = servers.SSLServer(port, factory, ctxFactory, backlog, interface)
        s.setParent(self.app)

    def unlistenSSL(self, port, interface=''):
        raise NotImplementedError()

    def connectWith(self, connectorType, *args, **kw):
        s = clients.GenericClient(connectorType,  *args, **kw)
        s.setParent(self.app)

    def unlistenSSL(self, port, interface=''):
        pass

    def connectUDP(self, remotehost, remoteport, protocol, localport=0,
                  interface='', maxPacketSize=8192):
        s = clients.GenericClient(connectorType,  *args, **kw)
        s.setParent(self.app)

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        s = clients.TCPClient(host, port, factory, timeout, bindAddress)
        s.setParent(self.app)

    def connectUNIX(self, address, factory, timeout=30):
        s = clients.UNIXClient(address, factory, timeout)
        s.setParent(self.app)


components.registerAdapter(service.IServiceCollection, ServiceNetwork)
