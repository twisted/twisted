# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
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
"""
Accesses the key agent for user authentication.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

from twisted.conch.ssh import agent, channel
from twisted.internet import protocol
from twisted.python import log

class SSHAgentClient(agent.SSHAgentClient):
    
    def __init__(self):
        agent.SSHAgentClient.__init__(self)
        self.blobs = []

    def getPublicKeys(self):
        return self.requestIdentities().addCallback(self._cbPublicKeys)

    def _cbPublicKeys(self, blobcomm):
        log.msg('got %i public keys' % len(blobcomm))
        self.blobs = [x[0] for x in blobcomm]

    def getPublicKey(self):
        if self.blobs:
            return self.blobs.pop(0)
        return None

class SSHAgentForwardingChannel(channel.SSHChannel):

    def channelOpen(self, specificData):
        cc = protocol.ClientCreator(reactor, SSHAgentForwardingLocal)
        d = cc.connectUNIX(os.environ['SSH_AUTH_SOCK'])
        d.addCallback(self._cbGotLocal)
        d.addErrback(lambda x:self.loseConnection())
        self.buf = ''

    def _cbGotLocal(self, local):
        self.local = local
        self.dataReceived = self.local.transport.write
        self.local.dataReceived = self.write
   
    def dataReceived(self, data): 
        self.buf += data

    def closed(self):
        if self.local:
            self.local.loseConnection()
            self.local = None

class SSHAgentForwardingLocal(protocol.Protocol): pass

