from twisted.python import components

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
