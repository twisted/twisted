
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
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
from twisted.protocols.protocol import Protocol
from twisted.python import usage

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

def success(response):
    print 'Success!  Got response:'
    print '---'
    if response is None:
        print None
    else:
        print string.join(response, '\n')
    print '---'


def fail(error):
    print 'Failed.  Error was:'
    print error
    from twisted.internet import reactor
    reactor.stop()


def showFiles(fileListProtocol):
    print 'Processed file listing:'
    for file in fileListProtocol.files:
        print '    %s: %d bytes, %s' \
              % (file['filename'], file['size'], file['date'])
    print 'Total: %d files' % (len(fileListProtocol.files))

def showBuffer(bufferProtocol):
    print 'Got data:'
    print bufferProtocol.buffer.getvalue()


class Options(usage.Options):
    optParameters = [['host', 'h', 'localhost'],
                     ['port', 'p', 21],
                     ['username', 'u', 'anonymous'],
                     ['password', None, 'twisted@'],
                     ['passive', None, 0],
                     ['debug', 'd', 1],
                    ]

    
# this connects the protocol to an FTP server running locally
def run():
    from twisted.internet import reactor
    
    # Get config
    config = Options()
    config.parseOptions()
    config.opts['port'] = int(config.opts['port'])
    config.opts['passive'] = int(config.opts['passive'])
    config.opts['debug'] = int(config.opts['debug'])
    
    # Create the client
    ftpClient = FTPClient(config.opts['username'], config.opts['password'], 
                          passive=config.opts['passive'])
    ftpClient.debug = config.opts['debug']
    reactor.clientTCP(config.opts['host'], config.opts['port'], ftpClient, 10.0)

    # Get the current working directory
    ftpClient.pwd().addCallbacks(success, fail).arm()

    # Get a detailed listing of the current directory
    d = ftpClient.list('.', FTPFileListProtocol())
    d.addCallbacks(showFiles, fail).arm()

    # Change to the parent directory
    ftpClient.cdup().addCallbacks(success, fail).arm()
    
    # Create a buffer
    proto = BufferingProtocol()

    # Get short listing of current directory, and quit when done
    d = ftpClient.nlst('.', proto)
    d.addCallbacks(showBuffer, fail)
    d.addCallback(lambda result: reactor.stop())
    d.arm()
    
    reactor.run()

# this only runs if the module was *not* imported
if __name__ == '__main__':
    run()
