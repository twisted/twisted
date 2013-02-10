# -*- test-case-name: twisted.internet.test.test_sendfile -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helper module for C{sendfile} support.
"""


from twisted.internet.defer import Deferred
from twisted.internet.abstract import _SendfileMarker
from twisted.internet.main import CONNECTION_LOST

try:
    from twisted.python._sendfile import sendfile
except ImportError:
    sendfile = None



class SendfileInfo(object):
    """
    Hold information about a sendfile transfer.

    @ivar started: Whether the sendfile transfer has started or not.
    @type started: C{bool}

    @ivar deferred: C{Deferred} fired when transfer is finished or when an
        error occurs.
    @type deferred: C{Deferred}

    @ivar fallback: C{Deferred} fired when first call of sendfile syscall
        fails.
    @type fallback: C{Deferred}

    @param offset: Current amount of data sent.
    @type offset: C{int}

    @param count: How many bytes of the file to send.
    @type count: C{int}
    """

    def __init__(self, fileObject):
        """
        @param fileObject: A file object, supported by sendfile(2) system call.
        @type fileObject: C{file}
        """
        self.file = fileObject
        self.offset = 0
        current = fileObject.tell()
        fileObject.seek(0, 2)
        self.count = fileObject.tell()
        fileObject.seek(current)
        self.deferred = Deferred()
        self.fallback = Deferred()
        self.started = False


    def done(self):
        """
        Check if the transfer is done.

        @return: C{True} if the whole file has been sent.
        @rtype: C{bool}
        """
        return self.count == self.offset


    def doSendfile(self, transport):
        """
        Wrapper around sendfile(2) call.

        @param transport: The C{FileDescriptor} to send the file on.
        """
        try:
            l, self.offset = sendfile(transport.fileno(), self.file.fileno(),
                                      self.offset, self.count)
        except IOError as e:
            from twisted.internet.tcp import EWOULDBLOCK
            if e.errno == EWOULDBLOCK:
                return
            elif not self.started:
                self.fallback.callback(None)
                return _SendfileMarker
            else:
                self.deferred.errback(e)
                return CONNECTION_LOST
        except Exception as e:
            self.deferred.errback(e)
            return e
        else:
            self.started = True
            if self.done():
                self.deferred.callback(None)



__all__ = ["sendfile", "SendfileInfo"]
