
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

from twisted.protocols.protocol import Protocol, Factory

### Protocol Implementation

# This is just about the simplest possible protocol

class Echo(Protocol):
    def dataReceived(self, data):
        "As soon as any data is received, write it back."
        self.transport.write(data)


# this runs the protocol on port 8000
def main():
    from twisted.internet.main import Application
    factory = Factory()
    factory.protocol = Echo
    app = Application("echo")
    app.listenOn(8000,factory)
    app.run(save=0)

# this only runs if the module was *not* imported
if __name__ == '__main__':
    main()
