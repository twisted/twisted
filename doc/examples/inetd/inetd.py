
import os

from twisted.internet.app import Application
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ServerFactory, ProcessProtocol
from twisted.python import log, usage

import inetdconf


class ServiceProcess(ProcessProtocol):
    def __init__(self, inetdProtocol):
        self.inetdProtocol = inetdProtocol

    def outReceived(self, data):
        # Pass the data back to the network client
        self.inetdProtocol.transport.write(data)

    def errReceived(self, data):
        log.msg("Process wrote to stderr:", repr(data))

    def processEnded(self, reason):
        self.inetdProtocol.transport.loseConnection()
    

class InetdProtocol(Protocol):
    def connectionMade(self):
        service = self.factory.service
        self.process = ServiceProcess(self)
        # FIXME: set uid/gid
        reactor.spawnProcess(self.process, service.program, 
                             args=service.programArgs, env=os.environ)
        
    def dataReceived(self, data):
        # Pass the data to the process's stdin
        self.process.transport.write(data)
        
    def connectionLost(self, reason):
        self.process.transport.loseConnection()


class InetdFactory(ServerFactory):
    protocol = InetdProtocol
    service = None
    
    def __init__(self, service):
        self.service = service


class InetdOptions(usage.Options):
    optParameters = [['file', 'f', '/etc/inetd.conf'],]


def main(options=None):
    if not options:
        options = InetdOptions()
        options.parseOptions()
    
    conf = inetdconf.InetdConf()
    conf.parseFile(open(options['file']))
    
    app = Application('tinetd')
    
    for service in conf.services:
        if service.protocol != 'tcp' or service.socketType != 'stream':
            log.msg('Skipping unsupported type/protocol: %s/%s'
                    % (service.socketType, service.protocol))
            continue

        print 'Adding service:', service.name, service.port, service.protocol
        factory = InetdFactory(service)
        app.listenTCP(service.port, factory)
    
    app.run(save=0)


if __name__ == '__main__':
    main()

