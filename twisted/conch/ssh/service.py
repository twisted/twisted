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

"""The parent class for all the SSH services.  Currently implemented services are: ssh-userauth and ssh-connection.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""


from twisted.python import log

class SSHService:
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

