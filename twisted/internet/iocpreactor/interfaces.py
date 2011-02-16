# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Interfaces for iocpreactor
"""


from zope.interface import Interface



class IReadHandle(Interface):
    def readFromHandle(bufflist, evt):
        """
        Read from this handle into the buffer list
        """



class IWriteHandle(Interface):
    def writeToHandle(buff, evt):
        """
        Write the buffer to this handle
        """



class IReadWriteHandle(IReadHandle, IWriteHandle):
    pass


