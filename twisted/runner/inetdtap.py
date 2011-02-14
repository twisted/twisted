# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""
Twisted inetd TAP support

Maintainer: Andrew Bennetts

Future Plans: more configurability.
"""

import os, pwd, grp, socket

from twisted.runner import inetd, inetdconf
from twisted.python import log, usage
from twisted.internet.protocol import ServerFactory
from twisted.application import internet, service as appservice

try:
    import portmap
    rpcOk = 1
except ImportError:
    rpcOk = 0


# Protocol map
protocolDict = {'tcp': socket.IPPROTO_TCP, 'udp': socket.IPPROTO_UDP}


class Options(usage.Options):

    optParameters = [
        ['rpc', 'r', '/etc/rpc', 'RPC procedure table file'],
        ['file', 'f', '/etc/inetd.conf', 'Service configuration file']
    ]

    optFlags = [['nointernal', 'i', "Don't run internal services"]]
    zsh_actions = {"file" : "_files -g '*.conf'"}

class RPCServer(internet.TCPServer):

    def __init__(self, rpcVersions, rpcConf, proto, service):
        internet.TCPServer.__init__(0, ServerFactory())
        self.rpcConf = rpcConf
        self.proto = proto
        self.service = service

    def startService(self):
        internet.TCPServer.startService(self)
        import portmap
        portNo = self._port.getHost()[2]
        service = self.service
        for version in rpcVersions:
            portmap.set(self.rpcConf.services[name], version, self.proto,
                        portNo)
            inetd.forkPassingFD(service.program, service.programArgs,
                                os.environ, service.user, service.group, p)

def makeService(config):
    s = appservice.MultiService()
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
            if config['nointernal']:
                continue

            # Internal services can use a standard ServerFactory
            if not inetd.internalProtocols.has_key(service.name):
                log.msg('Unknown internal service: ' + service.name)
                continue
            factory = ServerFactory()
            factory.protocol = inetd.internalProtocols[service.name]
        elif rpc:
            i = RPCServer(rpcVersions, rpcConf, proto, service)
            i.setServiceParent(s)
            continue
        else:
            # Non-internal non-rpc services use InetdFactory
            factory = inetd.InetdFactory(service)

        if protocol == 'tcp':
            internet.TCPServer(service.port, factory).setServiceParent(s)
        elif protocol == 'udp':
            raise RuntimeError("not supporting UDP")
    return s
