# -*- test-case-name: twisted.test.test_tpfile -*-

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

from twisted.internet import interfaces
from twisted.internet import defer

class FileSender:
    """A producer that sends the contents of a file to a consumer.
    
    This is a helper for protocols that, at some point, will take a
    file-like object, read its contents, and write them out to the network,
    optionally performing some transformation on the bytes in between.
    """
    __implements__ = (interfaces.IProducer,)
    
    CHUNK_SIZE = 2 ** 14
    
    lastSent = ''
    deferred = None

    def beginFileTransfer(self, file, consumer, transform):
        self.file = file
        self.consumer = consumer
        self.transform = transform
        
        self.consumer.registerProducer(self, 0)
        self.deferred = defer.Deferred()
        return self.deferred
    
    def resumeProducing(self):
        if self.file:
            chunk = self.file.read(self.CHUNK_SIZE)
        if not self.file or not chunk:
            self.file = None
            if self.deferred:
                self.deferred.callback(self.lastSent)
                self.deferred = None
            self.consumer.unregisterProducer()
            return
        
        chunk = self.transform(chunk)
        self.consumer.write(chunk)
        self.lastSent = chunk[-1]

    def pauseProducing(self):
        pass
    
    def stopProducing(self):
        if self.deferred:
            self.deferred.errback(Exception())
            self.deferred = None
