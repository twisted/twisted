# -*- test-case-name: twisted.test.test_rfc2822 -*-
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

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

class RFC2822Exception(Exception):
    pass

class HeaderGroup:
    map = None
    def __init__(self, headers):
        self.map = {}
        for s in headers:
            k, v = s.split(': ', 1)
            self.map.setdefault(k.lower(), []).append(v)
    
    def __getitem__(self, key):
        if isinstance(key, types.StringType):
            return self.map[key.lower()]
        raise TypeError, "HeaderGroup is indexable only by strings"
    
    def __getattr__(self, name):
        try:
            return self.map[key.lower().replace('_', '-')][0]
        except KeyError:
            return None
            # We could raise this exception, but I like
            # the None returning better at the moment.
            # raise AttributeError, name

class PartParser:
    def __init__(self, deferred):
        self.whenDone = deferred
    
    def connectionLost(self):
        if self.whenDone:
            self.whenDone.errback(RFC2822Exception("Premature lose of connection"))
            self.whenDone = None

class RFC2822Protocol(basic.LineReceiver, PartParser):
    state = 'headers'
    
    dispatch = {
        'headers': HeaderProtocol,
        
        # Different kinds of bodies
        'text': SinglepartProtocol,
        'image': SinglepartProtocol,
        'audio': SinglepartProtocol,
        'video': SinglepartProtocol,
        'application': SinglepartProtocol,
        
        'multipart': MultipartProtocol,
        'message': MessageProtocol,
    }
    
    def connectionMade(self):
        self.curParser = None
        self.headers = None
        self.body = None
        
        self.fini = {
            'headers': self._cbHeaders
        }

    def lineReceived(self, line):
        if not self.curParser:
            self.waiting = defer.Deferred()
            self.waiting.addCallback(self._cbFinish, self.fini[self.state])
            self.curParser = self.dispatch[self.state](d)
        
        self.curParser.lineReceived(line)

    def _cbFinish(self, result, callback):
        self.waiting = self.curParser = None
        callback(result)

    def _cbHeaders(self, result):
        self.headers = HeaderGroup(result)
        self.stateArgs = self._examineHeaders()
        self.state = 'body'

    def _examineHeaders(self):
        # Determine if this is a multipart message
        try:
            contentType = self.headers.content_type
        except KeyError:
            # It has no Content-Type header, therefore it is not MIME
            # therefore it is not multipart
            return None

        contentType = contentType.split(';')
        media = contentType[0].split('/')
        args = dict([arg.split('=') for arg in contentType[1:]])
        if len(media) != 2:
            # It is pre-MIME!
            return None
        else:
            if media[0] == 'multipart':
                return (
                    'multipart', args['boundary'],
                    self.headers.content_transfer_encoding,
                )
            else:
                raise RFC2822Exception, "Invalid media type: " + media[0]

class HeaderProtocol(basic.LineReceiver, PartParser):
    def connectionMade(self):
        self.lines = []
    
    def lineReceived(self, line):
        if line.startswith('\t'):
            try:
                self.lines[-1] += line
            except IndexError:
                self.whenDone.errback(RFC2822Exception("Illegal continuation"))
                self.whenDone = None
        elif not line:
            self.whenDone.callback(self.lines)
            self.whenDone = None
            self.transport.loseConnection()
        else:
            self.lines.append(line)

class SinglepartProtocol(basic.LineReceiver, PartParser):
    memoryLimit = 1024 * 1024
    
    def __init__(self, deferred, size):
        PartParser.__init__(self, deferred)
        self.size = size

    def connectionMade(self):
        if self.size is None or self.size > self.memoryLimit:
            self.body = TemporaryFile()
        else:
            self.body = StringIO()

    def lineReceived(self, line):
        assert self.body
        try:
            self.body.write(line + '\r\n')
        except:
            self.whenDone.errback(failure.Failure())
            self.whenDone = self.body = None

    def connectionLost(self):
        assert self.whenDone
        self.body.seek(0, 0)
        self.whenDone.callback(self.body)
        self.whenDone = self.body = None

class MultipartProtocol(basic.LineReceiver, PartParser):
    def __init__(self, deferred, boundary):
        PartParser.__init__(self, deferred)
        self.boundary = '--' + boundary
    
    def connectionMade(self):
        self.parts = []
        self.parser = None
    
    def lineReceived(self, line):
        if line == self.boundary:
            if self.parser:
                self.parser.transport.loseConnection()
            d = defer.Deferred()
            d.addCallback(self._cbPart)
            self.parser = RFC2822Protocol(d)
            self.parser.connectionMade()
        else:
            self.parser.lineReceived(line)
    
    def _cbPart(self, result):
        self.parts.append(result)
