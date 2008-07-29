# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""
Accesses the key agent for user authentication.

Maintainer: Paul Swartz
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

