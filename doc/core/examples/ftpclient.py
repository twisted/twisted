
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
from twisted.internet.protocol import Protocol, ClientCreator
from twisted.python import usage
from twisted.internet import reactor

# Standard library imports
import string
import sys
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class BufferingProtocol(Protocol):
    """Simple utility class that holds all data written to it in a buffer."""
    def __init__(self):
        self.buffer = StringIO()

    def dataReceived(self, data):
        self.buffer.write(data)

# Define some callbacks

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


def showFiles(result, fileListProtocol):
    print 'Processed file listing:'
    for file in fileListProtocol.files:
        print '    %s: %d bytes, %s' \
              % (file['filename'], file['size'], file['date'])
    print 'Total: %d files' % (len(fileListProtocol.files))

def showBuffer(result, bufferProtocol):
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

def run():
    # Get config
    config = Options()
    config.parseOptions()
    config.opts['port'] = int(config.opts['port'])
    config.opts['passive'] = int(config.opts['passive'])
    config.opts['debug'] = int(config.opts['debug'])
    
    # Create the client
    FTPClient.debug = config.opts['debug']
    creator = ClientCreator(reactor, FTPClient, config.opts['username'],
                            config.opts['password'], passive=config.opts['passive'])
    creator.connectTCP(config.opts['host'], config.opts['port']).addCallback(connectionMade)
    reactor.run()


def connectionMade(ftpClient):
    # Get the current working directory
    ftpClient.pwd().addCallbacks(success, fail)

    # Get a detailed listing of the current directory
    fileList = FTPFileListProtocol()
    d = ftpClient.list('.', fileList)
    d.addCallbacks(showFiles, fail, callbackArgs=(fileList,))

    # Change to the parent directory
    ftpClient.cdup().addCallbacks(success, fail)
    
    # Create a buffer
    proto = BufferingProtocol()

    # Get short listing of current directory, and quit when done
    d = ftpClient.nlst('.', proto)
    d.addCallbacks(showBuffer, fail, callbackArgs=(proto,))
    d.addCallback(lambda result: reactor.stop())


# this only runs if the module was *not* imported
if __name__ == '__main__':
    run()

