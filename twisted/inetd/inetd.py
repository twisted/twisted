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

import os, pwd, grp, traceback, socket, commands

from twisted.internet.app import Application
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.python import log, usage
from twisted.protocols import wire

import inetdconf

try:
    import portmap
    rpcOk = 1
except ImportError:
    rpcOk = 0

# A dict of known 'internal' services (i.e. those that don't involve spawning
# another process.
internalProtocols = {
    'echo': wire.Echo,
    'chargen': wire.Chargen,
    'discard': wire.Discard,
    'daytime': wire.Daytime,
    'time': wire.Time,
}
            
# Protocol map
protocolDict = {'tcp': socket.IPPROTO_TCP, 'udp': socket.IPPROTO_UDP}

def forkPassingFD(exe, args, env, user, group, fdesc):
    pid = os.fork()
    if pid == 0:    # Child
        try:
            # Close stdin/stdout (we keep stderr from the parent to report
            # errors with)
            for fd in range(2):
                os.close(fd)
            
            # Make the socket be fd 0 
            # (and fd 1, although I'm not sure if that matters)
            os.dup(fdesc.fileno())
            os.dup(fdesc.fileno())

            # Close unused file descriptors
            for fd in range(3, 256):
                try: os.close(fd)
                except: pass
            
            # Set uid/gid
            os.setgid(group)
            os.setuid(user)
            
            # Start the new process
            os.execvpe(exe, args, env)
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
        reactor.removeReader(fdesc)
        reactor.removeWriter(fdesc)
    

class InetdProtocol(Protocol):
    def connectionMade(self):
        # This is half-cannibalised from twisted.internet.process.Process
        service = self.factory.service
        forkPassingFD(service.program, service.programArgs, os.environ,
                      service.user, service.group, self.transport)


class InetdFactory(ServerFactory):
    protocol = InetdProtocol
    
    def __init__(self, service):
        self.service = service


def main(options=None):
    from twisted.inetd import tap
    # Parse options, read various config files
    if not options:
        options = tap.Options()
        options.parseOptions()
    
    app = Application('tinet')
    tap.updateApplications(app, options)
    app.run(save=0)


if __name__ == '__main__':
    main()

