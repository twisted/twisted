
import os, traceback, socket

from twisted.internet.app import Application
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ServerFactory, ProcessProtocol
from twisted.python import log, usage

import inetdconf


class InetdProtocol(Protocol):
    def connectionMade(self):
        # This is half-cannibalised from twisted.internet.process.Process
        service = self.factory.service
        pid = os.fork()
        if pid == 0:    # Child
            try:
                # Close stdin/stdout
                for fd in range(2):
                    os.close(fd)
                os.dup(self.transport.fileno())   # Should be fd 0
                os.dup(self.transport.fileno())   # Should be fd 1
                for fd in range(3, 256):
                    try: os.close(fd)
                    except: pass
                # FIXME: set uid/gid
                os.execvpe(service.program, service.programArgs, os.environ)
            except:
                # If anything goes wrong, just die.
                stderr = os.fdopen(2, 'w')
                stderr.write('Unable to spawn child:\n')
                traceback.print_exc(file=stderr)

                # Close the socket so the client doesn't think it's still
                # connected to a server
                try:
                    s = socket.fromfd(0, socket.AF_INET, socket.SOCK_STREAM)
                    s.shutdown(2)
                except:
                    pass
            os._exit(1)
        else:           # Parent
            reactor.removeReader(self.transport)
            reactor.removeWriter(self.transport)
        

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

