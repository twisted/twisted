# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""The parent class for all the SSH services.  Currently implemented services are: ssh-userauth and ssh-connection.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""


from twisted.python import log

class SSHService(log.Logger):
    name = None # this is the ssh name for the service
    protocolMessages = {} # these map #'s -> protocol names
    transport = None # gets set later

    def serviceStarted(self):
        """
        called when the service is active on the transport.
        """

    def serviceStopped(self):
        """
        called when the service is stopped, either by the connection ending
        or by another service being started
        """

    def logPrefix(self):
        return "SSHService %s on %s" % (self.name, self.transport.transport.logPrefix())

    def packetReceived(self, messageType, packet):
        """
        called when we receieve a packet on the transport
        """
        #print self.protocolMessages
        f = getattr(self,'ssh_%s' % self.protocolMessages[messageType][4:], None)
        if f:
            f(packet)            
        else:                     
            log.msg("couldn't handle", messageType)
            log.msg(repr(packet[1:]))
            self.transport.sendUnimplemented()

