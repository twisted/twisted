
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

"""HyperText Transfer Protocol implementation.

This is used by twisted.web.
"""

import string
import protocol
from twisted.protocols import basic
from cStringIO import StringIO
import rfc822

protocol_version = "HTTP/1.1"

_CONTINUE = 100
SWITCHING = 101

OK                              = 200
CREATED                         = 201
ACCEPTED                        = 202
NON_AUTHORITATIVE_INFORMATION   = 203
NO_CONTENT                      = 204
RESET_CONTENT                   = 205
PARTIAL_CONTENT                 = 206

MULTIPLE_CHOICE                 = 300
MOVED_PERMANENTLY               = 301
FOUND                           = 302
SEE_OTHER                       = 303
NOT_MODIFIED                    = 304
USE_PROXY                       = 305
TEMPORARY_REDIRECT              = 307

BAD_REQUEST                     = 400
UNAUTHORIZED                    = 401
PAYMENT_REQUIRED                = 402
FORBIDDEN                       = 403
NOT_FOUND                       = 404
NOT_ALLOWED                     = 405
NOT_ACCEPTABLE                  = 406
PROXY_AUTH_REQUIRED             = 407
REQUEST_TIMEOUT                 = 408
CONFLICT                        = 409
GONE                            = 410
LENGTH_REQUIRED                 = 411
PRECONDITION_FAILED             = 412
REQUEST_ENTITY_TOO_LARGE        = 413
REQUEST_URI_TOO_LONG            = 414
UNSUPPORTED_MEDIA_TYPE          = 415
REQUESTED_RANGE_NOT_SATISFIABLE = 416
EXPECTATION_FAILED              = 417

INTERNAL_SERVER_ERROR           = 500
NOT_IMPLEMENTED                 = 501
BAD_GATEWAY                     = 502
SERVICE_UNAVAILABLE             = 503
GATEWAY_TIMEOUT                 = 504
HTTP_VERSION_NOT_SUPPORTED      = 505
NOT_EXTENDED                    = 510

responses = {
    # 100
    _CONTINUE: "Continue",
    SWITCHING: "Switching Protocols",

    # 200
    OK: "OK!",
    CREATED: "Created.",
    ACCEPTED: "Accepted.",
    NON_AUTHORITATIVE_INFORMATION: "Non-Authoritative information",
    NO_CONTENT: "No content.",
    RESET_CONTENT: "Reset Content.",
    PARTIAL_CONTENT: "Partial content.",

    # 300
    MULTIPLE_CHOICE: "Multiple Choices",
    MOVED_PERMANENTLY: "Moved Permanently",
    FOUND: "Found.",
    SEE_OTHER: "See Other",
    NOT_MODIFIED: "Not Modified.",
    USE_PROXY: "Use Proxy.",
    # 306 not defined??
    TEMPORARY_REDIRECT: "Temporary Redirect.",

    # 400
    BAD_REQUEST: "Bad Request",
    UNAUTHORIZED: "Unauthorized",
    PAYMENT_REQUIRED: "Payment Required",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    NOT_ALLOWED: "Method not allowed",
    NOT_ACCEPTABLE: "Not Acceptable",
    PROXY_AUTH_REQUIRED: "Proxy authentication required.",
    REQUEST_TIMEOUT: "Request Timeout",
    CONFLICT: "Conflict",
    GONE: "Gone",
    LENGTH_REQUIRED: "Length Required",
    PRECONDITION_FAILED: "Precondition Failed.",
    REQUEST_ENTITY_TOO_LARGE: "Request Entity Too Large",
    REQUEST_URI_TOO_LONG: "Request-URI Too Long",
    UNSUPPORTED_MEDIA_TYPE: "Unsupported Media Type",
    REQUESTED_RANGE_NOT_SATISFIABLE: "Requested range not satisfiable.",
    EXPECTATION_FAILED: "Expectation Failed.",

    # 500
    INTERNAL_SERVER_ERROR: "Internal Server Error",
    NOT_IMPLEMENTED: "Not Implemented",
    BAD_GATEWAY: "Bad Gateway",
    SERVICE_UNAVAILABLE: "Service Unavailable",
    GATEWAY_TIMEOUT: "Gateway Timeout",
    HTTP_VERSION_NOT_SUPPORTED: "HTTP Version Not Supported",

    NOT_EXTENDED: "Not Extended"}







class HTTPClient(basic.LineReceiver):
    """A client for HTTP
    """
    length = None
    firstLine = 1
    __buffer = ''

    def sendCommand(self, command, path):
        self.transport.write('%s %s HTTP/1.0\r\n' % (command, path))

    def sendHeader(self, name, value):
        self.transport.write('%s: %s\r\n' % (name, value))

    def endHeaders(self):
        self.transport.write('\r\n')

    def lineReceived(self, line):
        if self.firstLine:
            self.firstLine = 0
            version, status, message = string.split(line, None, 2)
            self.handleStatus(version, status, message)
            return
        if line:
            key, val = string.split(line, ': ', 1)
            self.handleHeader(key, val)
            if string.lower(key) == 'content-length':
                self.length = int(val)
        else:
            self.handleEndHeaders()
            self.setRawMode()

    def connectionLost(self):
        if self.__buffer:
            b = self.__buffer
            self.__buffer = ''
            self.handleResponse(b)

    def connectionMade(self):
        pass

    handleStatus = handleHeader = handleEndHeaders = lambda *args: None

    def rawDataReceived(self, data):
        if self.length is not None:
            data, rest = data[:self.length], data[self.length:]
            self.length = self.length - len(data)
        else:
            rest = ''
        self.__buffer = self.__buffer + data
        if self.length == 0:
            b = self.__buffer
            self.__buffer = ''
            self.handleResponse(b)
            self.setLineMode(rest)


class HTTP(basic.LineReceiver):
    """A receiver for HTTP requests.
    """
    length = 0
    __header = ''
    __first_line = 1

    def __init__(self):
        self.received = {}

    def sendStatus(self, code, resp=''):
        self.transport.write('HTTP/1.0 %s %s\r\n' % (code, resp))

    def sendHeader(self, name, value):
        self.transport.write('%s: %s\r\n' % (name, value))

    def endHeaders(self):
        self.transport.write('\r\n')

    def sendError(self, code, resp=''):
        self.sendStatus(code, resp)
        self.endHeaders()

    def lineReceived(self, line):
        if self.__first_line:
	    # IE sends an extraneous empty line (\r\n) after a POST request;
	    # eat up such a line, but only ONCE
	    if not line and self.__first_line == 1:
	        self.__first_line = 2
		return
            self.__first_line = 0
            parts = string.split(line)
            if len(parts)<3:
                parts.append('HTTP/0.9') # isn't backwards compat great!
            if len(parts) != 3:
                self.sendError(405, 'Bad command')
                #raise ValueError(repr(parts))
                self.transport.loseConnection()
                return
            command, request, version = parts
            self.__command = command
            self.__path = request
            self.__version = version
            if version == 'HTTP/0.9':
                self.allHeadersReceived()
                self.allContentReceived()
        elif line == '':
            if self.__header:
                self.headerReceived(self.__header)
            self.__header = ''
            self.allHeadersReceived()
            if self.length == 0:
                self.allContentReceived()
            else:
                self.setRawMode()
        elif line[0] in ' \t':
            self.__header = self.__header+'\n'+line
        else:
            if self.__header:
                self.headerReceived(self.__header)
            self.__header = line


    def headerReceived(self, line):
        """Do pre-processing (for content-length) and store this header away.
        """
        header, data = string.split(line, ':', 1)
        header = string.lower(header)
        data = string.strip(data)
        if header == 'content-length':
            self.length = int(data)
        self.received[header] = data

    def allContentReceived(self):
        # reset ALL state variables, in order to not propagate any
        # bugs across requests
        self.length = 0
        self.__header = ''
        self.__first_line = 1
        data = self.__content.getvalue()
        command = self.__command
        path = self.__path
        version = self.__version
        del self.__content, self.__command, self.__path, self.__version
        self.requestReceived(command, path, version, data)

    def rawDataReceived(self, data):
        if len(data) < self.length:
            self.handleContentChunk(data)
            self.length = self.length - len(data)
        else:
            self.handleContentChunk(data[:self.length])
            extraneous = data[self.length:]
            self.allContentReceived()
            self.setLineMode(extraneous)

    def allHeadersReceived(self):
        command = self.__command
        path = self.__path
        version = self.__version
        del self.__command, self.__path, self.__version
        self.__command, self.__path, self.__version = \
                        command, path, version
        self.__content = StringIO()


    __content = None

    def handleContentChunk(self, data):
        self.__content.write(data)

    ### Externally Callable Interface

    def getHeader(self, key):
        """Get a header that was sent from the network.
        """
        return self.received.get(string.lower(key))
