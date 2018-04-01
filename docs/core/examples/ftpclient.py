
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
An example of using the FTP client
"""
from __future__ import print_function

# Twisted imports
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol
from twisted.internet.protocol import Protocol, ClientCreator
from twisted.python import usage
from twisted.internet import reactor

# Standard library imports
import sys
from io import BytesIO


class BufferingProtocol(Protocol):
    """Simple utility class that holds all data written to it in a buffer."""
    def __init__(self):
        self.buffer = BytesIO()

    def dataReceived(self, data):
        self.buffer.write(data)

# Define some callbacks

def success(response):
    print('Success!  Got response:')
    print('---')
    if response is None:
        print(None)
    else:
        print("\n".join(response))
    print('---')


def fail(error):
    print('Failed.  Error was:')
    print(error)

def showFiles(result, fileListProtocol):
    print('Processed file listing:')
    for file in fileListProtocol.files:
        print('    {}: {} bytes, {}'.format(
              file['filename'], file['size'], file['date']))
    print('Total: {} files'.format(len(fileListProtocol.files)))

def showBuffer(result, bufferProtocol):
    print('Got data:')
    print(bufferProtocol.buffer.getvalue())


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
    creator.connectTCP(config.opts['host'], config.opts['port']).addCallback(connectionMade).addErrback(connectionFailed)
    reactor.run()

def connectionFailed(f):
    print("Connection Failed:", f)
    reactor.stop()

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

