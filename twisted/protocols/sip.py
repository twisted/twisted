# -*- test-case-name: twisted.test.test_sip -*-

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

"""Session Initialization Protocol."""

# twisted imports
from twisted.python import log
from twisted.internet import protocol

# sibling imports
import basic


class Message:
    """A SIP message."""

    length = None
    
    def __init__(self):
        self.headers = []
        self.body = ""
        self.finished = 0
    
    def addHeader(self, name, value):
        name = name.lower()
        if name == "content-length":
            self.length = int(value)
        self.headers.append((name, value))

    def bodyDataReceived(self, data):
        self.body += data
    
    def creationFinished(self):
        if (self.length != None) and (self.length != len(self.body)):
            raise ValueError, "wrong body length"
        self.finished = 1

    def toString(self):
        s = "%s\r\n" % self._getHeaderLine()
        for n, v in self.headers:
            s += "%s: %s\r\n" % (n, v)
        s += "\r\n"
        s += self.body
        return s


class Request(Message):

    def __init__(self, method, uri, version="SIP/2.0"):
        Message.__init__(self)
        self.method = method
        self.uri = uri

    def __repr__(self):
        return "<SIP Request %d:%s %s>" % (id(self), self.method, self.uri)

    def _getHeaderLine(self):
        return "%s %s SIP/2.0" % (self.method, self.uri)


class Response(Message):

    def __init__(self, code, phrase, version="SIP/2.0"):
        Message.__init__(self)
        self.code = code
        self.phrase = phrase

    def __repr__(self):
        return "<SIP Response %d:%s>" % (id(self), self.code)

    def _getHeaderLine(self):
        return "SIP/2.0 %s %s" % (self.code, self.phrase)


class MessagesParser(basic.LineReceiver):
    """A SIP messages parser.

    Expects dataReceived, dataDone repeatedly,
    in that order. Shouldn't be connected to actual transport.
    """

    version = "SIP/2.0"
    acceptResponses = 1
    acceptRequests = 1
    state = "firstline" # or "headers", "body" or "invalid"
    
    def __init__(self, messageReceivedCallback):
        self.messageReceived = messageReceivedCallback
        self.reset()

    def reset(self, remainingData=""):
        self.state = "firstline"
        self.length = None # body length
        self.bodyReceived = 0 # how much of the body we received
        self.message = None
        self.setLineMode(remainingData)
    
    def invalidMessage(self):
        self.state = "invalid"
        self.setRawMode()
    
    def dataDone(self):
        # clear out any buffered data that may be hanging around
        self.clearLineBuffer()
        if self.state == "firstline":
            return
        if self.state != "body":
            self.reset()
            return
        if self.length == None:
            # no content-length header, so end of data signals message done
            self.messageDone()
        elif self.length < self.bodyReceived:
            # aborted in the middle
            self.reset()
        else:
            # we have enough data and message wasn't finished? something is wrong
            assert 0, "this should never happen"
    
    def dataReceived(self, data):
        try:
            basic.LineReceiver.dataReceived(self, data)
        except:
            log.err()
            self.invalidMessage()
    
    def handleFirstLine(self, line):
        """Expected to create self.message."""
        raise NotImplementedError

    def lineLengthExceeded(self):
        self.invalidMessage()
    
    def lineReceived(self, line):
        if self.state == "firstline":
            line = line.rstrip("\n\r")
            if not line:
                return
            try:
                a, b, c = line.split(" ", 2)
            except ValueError:
                self.invalidMessage()
                return
            if a == "SIP/2.0" and self.acceptResponses:
                # response
                try:
                    code = int(b)
                except ValueError:
                    self.invalidMessage()
                    return
                self.message = Response(code, c)
            elif c == "SIP/2.0" and self.acceptRequests:
                self.message = Request(a, b)
            else:
                self.invalidMessage()
                return
            self.state = "headers"
            return
        else:
            assert self.state == "headers"
        if line:
            # XXX support multi-line headers
            try:
                name, value = line.split(":", 1)
            except ValueError:
                self.invalidMessage()
                return
            self.message.addHeader(name, value.lstrip())
            if name.lower() == "content-length":
                try:
                    self.length = int(value.lstrip())
                except ValueError:
                    self.invalidMessage()
                    return
        else:
            # CRLF, we now have message body until self.length bytes,
            # or if no length was given, until there is no more data
            # from the connection sending us data.
            self.state = "body"
            if self.length == 0:
                self.messageDone()
                return
            self.setRawMode()

    def messageDone(self, remainingData=""):
        assert self.state == "body"
        self.message.creationFinished()
        self.messageReceived(self.message)
        self.reset(remainingData)
    
    def rawDataReceived(self, data):
        assert self.state in ("body", "invalid")
        if self.state == "invalid":
            return
        if self.length == None:
            self.message.bodyDataReceived(data)
        else:
            dataLen = len(data)
            expectedLen = self.length - self.bodyReceived
            if dataLen > expectedLen:
                self.message.bodyDataReceived(data[:expectedLen])
                self.messageDone(data[expectedLen:])
                return
            else:
                self.bodyReceived += dataLen
                self.message.bodyDataReceived(data)
                if self.bodyReceived == self.length:
                    self.messageDone()


class BaseSIP(protocol.DatagramProtocol):
    """Base class for SIP clients and servers."""
    
    def __init__(self):
        self.messages = []
        self.parser = MessagesParser(self.messages.append)
    
    def datagramReceived(self, data, addr):
        self.parser.dataReceived(data)
        self.parser.dataDone()
        for m in self.messages:
            if isinstance(m, Request):
                f = getattr(self, "handle_%s_request" % m.method, self.handle_request_default)
                f(m, addr)
            else:
                f = getattr(self, "handle_%s_response" % m.code, self.handle_response_default)
                f(m, addr)
        self.messages[:] = []

    def handle_response_default(self, message, addr):
        print "Received response %s from %s" % (message, addr)

    def handle_request_default(self, message, addr):
        print "Received request %s from %s" % (message, addr)


if __name__ == '__main__':
    import sys
    from twisted.internet import reactor
    log.startLogging(sys.stdout)
    reactor.listenUDP(5060, SIPServer())
    reactor.run()
