
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

"""
An example client. Run simpleserv.py first before running this.
"""

from twisted.internet.protocol import Protocol, Factory


# a client protocol

class EchoClient(Protocol):
    """Once connected, send a message, then print the result."""
    
    def connectionMade(self):
        self.transport.write("hello, world!")
    
    def dataReceived(self, data):
        "As soon as any data is received, write it back."
        print "Server said:", data
        self.transport.loseConnection()
    
    def connectionLost(self, reason):
        print "connection lost"
        from twisted.internet import reactor
        reactor.stop()


class EchoFactory(protocol.ClientFactory):
    
    def connectionFailed(self, connector, reason):
        print "Connection failed - goodbye!"
        from twisted.internet import reactor
        reactor.stop()


# this connects the protocol to a server runing on port 8000
def main():
    # install default reactor
    from twisted.internet import default
    default.install()

    from twisted.internet import reactor
    p = EchoClient()
    reactor.clientTCP("localhost", 8000, p)
    reactor.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    main()
