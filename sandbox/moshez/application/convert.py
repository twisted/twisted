from twisted.application import clients, servers, app

def convert(oldApp):
    '''
    This function might damage oldApp beyond repair: services
    that other parts might be depending on might be missing.
    It is not safe to use oldApp after it has been converted.
    In case this behaviour is not desirable, pass a deep copy
    of the old application
    '''
    ret = app.Application(oldApp.name, oldApp.uid, oldApp.gid)
    ret.processName = oldApp.processName
    for (portType,args,kw) in oldApp.extraPorts:
        servers.GenericServer(portType, *args, **kw).setParent(ret)
    for (portType,args,kw) in oldApp.extraConnectors:
        clients.GenericClient(portType, *args, **kw).setParent(ret)
    for (pList, klass) in [(oldApp.tcpPorts, servers.TCPServer),
                           (oldApp.unixPorts, servers.UNIXServer),
                           (oldApp.udpPorts, servers.UDPServer),
                           (oldApp.sslPorts, servers.SSLServer),
                           (oldApp.udpConnectors, clients.UDPClient),
                           (oldApp.tcpConnectors, clients.TCPClient),
                           (oldApp.sslConnectors, clients.SSLClient),
                           (oldApp.unixConnectors, clients.UNIXClient),
                          ]
        for args in plist:
            klass(*args).setParent(ret)
    for service in oldApp.services.values():
        service.disownServiceParent()
        service.setParent(ret)
    return ret
