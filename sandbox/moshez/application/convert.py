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
                           (oldApp.extraConnectors, clients.GenericClient),]:
        for (portType, args, kw) in pList:
            klass(portType, args, kw).setServiceParent(ret)
    for (name, klass) in mapping:
        for args in getattr(oldApp, name):
            klass(*args).setServiceParent(ret)
    for service in ret:
        if isinstance(service, servers._AbstractServer):
            service.privileged = 1
    for service in oldApp.services.values():
        service.disownServiceParent()
        service.setServiceParent(ret)
    return ret
