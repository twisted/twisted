from twisted.application import clients, servers, app

mapping = []
for tran in 'tcp unix udp ssl'.split():
    mapping.append((tran+'Ports', getattr(servers, tran.upper()+'Server')))
    mapping.append((tran+'Connectors', getattr(clients, tran.upper()+'Client')))

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
    for (pList, klass) in [(oldApp.extraPorts, servers.GenericServer),
                           (oldApp.extraConnectors, servers.GenericClient),]:
        for (portType, args, kw) in pList:
            klass(portType, args, kw).setServiceParent(ret)
    for (name, klass) in mapping:
        for args in getattr(oldApp, name):
            klass(*args).setServiceParent(ret)
    for service in oldApp.services.values():
        service.disownServiceParent()
        service.setParent(ret)
    return ret
