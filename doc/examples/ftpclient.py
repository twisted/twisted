
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
An example of using the FTP client
"""

# Twisted imports
from twisted.protocols.ftp import FTPClient
from twisted.protocols.protocol import Protocol
from twisted.internet import main, tcp

# Standard library imports
import string
import sys
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class BufferingProtocol(Protocol):
    def __init__(self):
        self.buffer = StringIO()

    def dataReceived(self, data):
        self.buffer.write(data)

def success(response, buffer=None):
    print 'Success!  Got response:'
    print '---'
    if response is None:
        print None
    else:
        print string.join(response, '\n')
    print '---'
    if buffer:
        print 'Buffer is:'
        print buffer.getvalue()
    print '---'

def fail(error):
    print 'Failed.  Error was:'
    print error
    main.shutDown()

# this connects the protocol to an FTP server running locally
def run():
    ftpClient = FTPClient('andrew', 'XXXX', passive=0)
    ftpClient.debug = 1
    tcp.Client("localhost", 21, ftpClient)

    # Create a buffer
    proto = BufferingProtocol()
    
    # Get the current working directory
    ftpClient.pwd().addCallbacks(success, fail)

    # Get a detailed listing of the current directory
    ftpClient.list('.', proto).addCallbacks(success, 
                                            fail, 
                                            callbackArgs=(proto.buffer,)).arm()

    # Change to the parent directory
    ftpClient.cdup().addCallbacks(success, fail).arm()
    
    # Create a fresh buffer
    proto = BufferingProtocol()

    # Get short listing of current directory, and quit when done
    d = ftpClient.nlst('.', proto)
    #d.addCallbacks(fail, fail)
    d.addCallbacks(success, fail, callbackArgs=(proto.buffer,))
    d.addCallbacks(lambda result: main.shutDown())
    d.arm()
    
    main.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    run()
