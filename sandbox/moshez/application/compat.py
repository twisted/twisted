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
from twisted.application import internet, service
from twisted.persisted import sob

class IOldApplication(components.Interface):

    def listenWith(self, portType, *args, **kw):
        pass

    def listenTCP(self, port, factory, backlog=5, interface=''):
        pass

    def listenUNIX(self, filename, factory, backlog=5, mode=0666):
        pass

    def listenUDP(self, port, proto, interface='', maxPacketSize=8192):
        pass

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
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

    def addService(self, service):
        pass

    def getServiceNamed(self, name):
        pass

    def unlistenWith(self, portType, *args, **kw):
        pass

    def unlistenTCP(self, port, interface=''):
        pass

    def unlistenUNIX(self, filename):
        pass

    def unlistenUDP(self, port, interface=''):
        pass

    def unlistenSSL(self, port, interface=''):
        pass




class ServiceNetwork:

    __implements__ = IOldApplication,

    def __init__(self, app):
        self.app = service.IServiceCollection(app)

    def listenWith(self, portType, *args, **kw):
        internet.GenericServer(portType, *args, **kw).setServiceParent(self.app)

    def listenTCP(self, port, factory, backlog=5, interface=''):
        s = internet.TCPServer(port, factory, backlog, interface)
        s.setServiceParent(self.app)

    def listenUNIX(self, filename, factory, backlog=5, mode=0666):
        s = internet.UNIXServer(filename, factory, backlog, mode)
        s.setServiceParent(self.app)

    def listenUDP(self, port, proto, interface='', maxPacketSize=8192):
        s = internet.UDPServer(port, proto, interface, maxPacketSize)
        s.setServiceParent(self.app)

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        s = internet.SSLServer(port, factory, ctxFactory, backlog, interface)
        s.setServiceParent(self.app)

    def connectWith(self, connectorType, *args, **kw):
        s = internet.GenericClient(connectorType,  *args, **kw)
        s.setServiceParent(self.app)

    def connectUDP(self, remotehost, remoteport, protocol, localport=0,
                  interface='', maxPacketSize=8192):
        s = internet.UDPClient(remotehost, remoteport, protocol, localport,
                               interface, maxPacketSize)
        s.setServiceParent(self.app)

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        s = internet.TCPClient(host, port, factory, timeout, bindAddress)
        s.setServiceParent(self.app)

    def connectUNIX(self, address, factory, timeout=30):
        s = internet.UNIXClient(address, factory, timeout)
        s.setServiceParent(self.app)

    def addService(self, service):
        self.app.addService(service)

    def getServiceNamed(self, name):
        return self.app.getServiceNamed(name)

    def unlistenWith(self, portType, *args, **kw):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenTCP(self, port, interface=''):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenUNIX(self, filename):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenUDP(self, port, interface=''):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenSSL(self, port, interface=''):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)


components.registerAdapter(ServiceNetwork,
                           service.IServiceCollection, IOldApplication)


mapping = []
for tran in 'tcp unix udp ssl'.split():
    mapping.append((tran+'Ports', getattr(internet, tran.upper()+'Server')))
    mapping.append((tran+'Connectors',getattr(internet, tran.upper()+'Client')))

def convert(oldApp):
    '''
    This function might damage oldApp beyond repair: services
    that other parts might be depending on might be missing.
    It is not safe to use oldApp after it has been converted.
    In case this behaviour is not desirable, pass a deep copy
    of the old application
    '''
    ret = service.Application(oldApp.name, oldApp.uid, oldApp.gid)
    service.IProcess(ret).processName = oldApp.processName
    for (pList, klass) in [(oldApp.extraPorts, internet.GenericServer),
                           (oldApp.extraConnectors, internet.GenericClient),]:
        for (portType, args, kw) in pList:
            s = klass(portType, *args, **kw)
            s.setServiceParent(service.IServiceCollection(ret))
    for (name, klass) in mapping:
        for args in getattr(oldApp, name):
            klass(*args).setServiceParent(service.IServiceCollection(ret))
    for service in IServiceCollection(ret):
        if isinstance(service, internet._AbstractServer):
            service.privileged = 1
    for service in oldApp.services.values():
        service.disownServiceParent()
        service.setServiceParent(service.IServiceCollection(ret))
    return ret
