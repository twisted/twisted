# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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

import pwd, grp
from twisted.inetd import inetd, inetdconf
from twisted.python import log, usage


class Options(usage.Options):

    optParameters = [['rpc', 'r', '/etc/rpc'],
                     ['file', 'f', '/etc/inetd.conf'],]


def updateApplication(app, config):
    
    conf = inetdconf.InetdConf()
    conf.parseFile(open(config['file']))

    rpcConf = inetdconf.RPCServicesConf()
    try:
        rpcConf.parseFile(open(config['rpc']))
    except:
        # We'll survive even if we can't read /etc/rpc
        log.deferr()
    
    for service in conf.services:
        rpc = service.protocol.startswith('rpc/')
        protocol = service.protocol

        if rpc and not rpcOk:
            log.msg('Skipping rpc service due to lack of rpc support')
            continue

        if rpc:
            # RPC has extra options, so extract that
            protocol = protocol[4:]     # trim 'rpc/'
            if not protocolDict.has_key(protocol):
                log.msg('Bad protocol: ' + protocol)
                continue
            
            try:
                name, rpcVersions = service.name.split('/')
            except ValueError:
                log.msg('Bad RPC service/version: ' + service.name)
                continue

            if not rpcConf.services.has_key(name):
                log.msg('Unknown RPC service: ' + repr(service.name))
                continue

            try:
                if '-' in rpcVersions:
                    start, end = map(int, rpcVersions.split('-'))
                    rpcVersions = range(start, end+1)
                else:
                    rpcVersions = [int(rpcVersions)]
            except ValueError:
                log.msg('Bad RPC versions: ' + str(rpcVersions))
                continue
            
        if (protocol, service.socketType) not in [('tcp', 'stream'),
                                                  ('udp', 'dgram')]:
            log.msg('Skipping unsupported type/protocol: %s/%s'
                    % (service.socketType, service.protocol))
            continue

        # Convert the username into a uid (if necessary)
        try:
            service.user = int(service.user)
        except ValueError:
            try:
                service.user = pwd.getpwnam(service.user)[2]
            except KeyError:
                log.msg('Unknown user: ' + service.user)
                continue

        # Convert the group name into a gid (if necessary)
        if service.group is None:
            # If no group was specified, use the user's primary group
            service.group = pwd.getpwuid(service.user)[3]
        else:
            try:
                service.group = int(service.group)
            except ValueError:
                try:
                    service.group = grp.getgrnam(service.group)[2]
                except KeyError:
                    log.msg('Unknown group: ' + service.group)
                    continue

        if service.program == 'internal':
            # Internal services can use a standard ServerFactory
            if not internalProtocols.has_key(service.name):
                log.msg('Unknown internal service: ' + service.name)
                continue
            factory = ServerFactory()
            factory.protocol = internalProtocols[service.name]
        elif rpc:
            proto = protocolDict[protocol]
            p = reactor.listenTCP(0, ServerFactory())
            portNo = p.getHost()[2]
            for version in rpcVersions:
                portmap.set(rpcConf.services[name], version, proto, portNo)
            forkPassingFD(service.program, service.programArgs, os.environ,
                          service.user, service.group, p)
            continue
        else:
            # Non-internal non-rpc services use InetdFactory
            factory = inetd.InetdFactory(service)

        if protocol == 'tcp':
            app.listenTCP(service.port, factory)
        elif protocol == 'udp':
            app.listenUDP(service.port, factory)

