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

import os

from twisted.internet import process, reactor
from twisted.internet.protocol import Protocol, ServerFactory
from twisted.protocols import wire

# A dict of known 'internal' services (i.e. those that don't involve spawning
# another process.
internalProtocols = {
    'echo': wire.Echo,
    'chargen': wire.Chargen,
    'discard': wire.Discard,
    'daytime': wire.Daytime,
    'time': wire.Time,
}
            

class InetdProtocol(Protocol):
    """Forks a child process on connectionMade, passing the socket as fd 0."""
    def connectionMade(self):
        sockFD = self.transport.fileno()
        childFDs = {0: sockFD, 1: sockFD}
        if self.factory.stderrFile:
            childFDs[2] = self.factory.stderrFile.fileno()

        service = self.factory.service
        uid = service.user
        gid = service.group
        # don't tell Process to change our UID/GID if it's what we
        # already are
        if uid == os.getuid():
            uid = None
        if gid == os.getgid():
            gid = None
        process.Process(None, service.program, service.programArgs, os.environ,
                        None, None, uid, gid, childFDs)

        reactor.removeReader(self.transport)
        reactor.removeWriter(self.transport)
                        

class InetdFactory(ServerFactory):
    protocol = InetdProtocol
    stderrFile = None
    
    def __init__(self, service):
        self.service = service
