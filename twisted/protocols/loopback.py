
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

# These class's names should have been based on Onanism, but were
# censored by the PSU

import protocol # See?  Their security protocol at work!!

class LoopbackRelay(protocol.Transport):

    buffer = ''
    shouldLose = 0

    def __init__(self, target):
        self.target = target

    def write(self, data):
        #print "writing", `data`
        self.buffer = self.buffer + data

    def clearBuffer(self):
        try:
            self.target.dataReceived(self.buffer)
        finally:
            self.buffer = ''
        if self.shouldLose:
            self.target.connectionLost()

    def loseConnection(self):
        self.shouldLose = 1

def loopback(server, client):
    serverToClient = LoopbackRelay(client)
    clientToServer = LoopbackRelay(server)
    server.makeConnection(serverToClient)
    client.makeConnection(clientToServer)
    while 1:
        serverToClient.clearBuffer()
        clientToServer.clearBuffer()
        if serverToClient.shouldLose or clientToServer.shouldLose:
            break
