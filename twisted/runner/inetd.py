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

"""Twisted inetd.

Stability: semi-stable

Maintainer: U{Andrew Bennetts<spiv@twistedmatrix.com>}

Future Plans: Bugfixes.  Specifically for UDP and Sun-RPC, which don't work
correctly yet.
"""

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
    """Run exe as a child process, passing fdesc as fd 0.
    
    This will also make sure that fdesc is removed from the parent's reactor.
    """
    # This is half-cannibalised from twisted.internet.process.Process
    pid = os.fork()
    if pid == 0:    # Child
        try:
            # Make the socket be fd 0 
            # (and fd 1, although I'm not sure if that matters)
            # (we keep stderr from the parent to report errors with)
            os.dup2(fdesc.fileno(), 0)
            os.dup2(fdesc.fileno(), 1)

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
            from sys import stderr
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
    """Forks a child process on connectionMade, passing the socket as fd 0."""
    def connectionMade(self):
        service = self.factory.service
        forkPassingFD(service.program, service.programArgs, os.environ,
                      service.user, service.group, self.transport)


class InetdFactory(ServerFactory):
    protocol = InetdProtocol
    
    def __init__(self, service):
        self.service = service
