#! /usr/bin/python

"""
This is a Twisted wrapper for the Python binding to FUSD, which is a system
for implementing Linux device drivers in userspace. The five
character-device system calls (open/close/read/write/ioctl) go to a kernel
module, which sends messages over a socket to a userspace program which will
provide the results. With fusd.py (the python binding), those programs can
be written in Python. With this file, those python programs can use the
Twisted event loop (and all the protocols that Twisted offers).

FUSD: http://www.circlemud.org/~jelson/software/fusd/
The FUSD python binding is in the CVS tree, under fusd/python/ .

 -Brian Warner
"""


import fusd
from twisted.internet import abstract, fdesc, main
from twisted.python import failure

OpenFile = fusd.OpenFile

class Device(fusd.Device, abstract.FileDescriptor):
    def __init__(self, fileClass, name, mode):
        abstract.FileDescriptor.__init__(self)
        fusd.Device.__init__(self, name, mode)
        self.openFileClass = fileClass
        self.connected = 1
        self.startReading()

    def fileno(self):
        return self.handle

    def doRead(self):
        self.dispatch()

    def loseConnection(self, connDone=failure.Failure(main.CONNECTION_DONE)):
        self.disconnecting = 1
        self.stopReading()
        if self.connected:
            self.reactor.callLater(0, self.connectionLost, connDone)

    def connectionLost(self, reason):
        abstract.FileDescriptor.connectionLost(self, reason)
        self.unregister()
