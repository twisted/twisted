
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

"""This is a web-sever which integrates with the twisted.internet
infrastructure.  """

# System Imports

import base64
import cStringIO
StringIO = cStringIO
del cStringIO
import string
import socket
import errno
import traceback
import types
import os
import sys
import urllib
import cgi
import cPickle
import copy
import time

# Twisted Imports
from twisted.spread import pb
from twisted.internet import tcp, passport
from twisted.protocols import http, protocol
from twisted.python import log, threadable, reflect
from twisted import copyright

# Sibling Imports
import error
import resource

#some useful constants
NOT_DONE_YET = 1

weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
monthname = [None,
             'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def date_time_string(msSinceEpoch=None):
    "Mangled HTTP date goodness..."
    if msSinceEpoch == None:
        msSinceEpoch = time.time()
    year, month, day, hh, mm, ss, wd, y, z = time.gmtime(msSinceEpoch)
    s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
        weekdayname[wd],
        day, monthname[month], year,
        hh, mm, ss)
    return s



class Request(pb.Copyable, http.HTTP):

    code = http.OK
    method = "(no method yet)"
    clientproto = "(no clientproto yet)"
    uri = "(no uri yet)"

    def getStateToCopyFor(self, issuer):
        x = copy.copy(self.__dict__)
        del x['transport']
        # XXX refactor this attribute out; it's from protocol
        del x['server']
        del x['site']
        x['remote'] = pb.ViewPoint(issuer, self)
        return x

    # HTML generation helpers

    def sibLink(self, name):
        "Return the text that links to a sibling of the requested resource."
        if self.postpath:
            return (len(self.postpath)*"../") + name
        else:
            return name

    def childLink(self, name):
        "Return the text that links to a child of the requested resource."
        lpp = len(self.postpath)
        if lpp > 1:
            return ((lpp-1)*"../") + name
        elif lpp == 1:
            return name
        else: # lpp == 0
            if len(self.prepath):
                return self.prepath[-1] + '/' + name
            else:
                return name

    def _parse_argstring(self, argstring, split=string.split):
        for kvp in split(argstring, '&'):
            keyval = map(urllib.unquote, split(kvp, '='))
            if len(keyval) != 2:
                continue
            key, value = keyval
            arg = self.args[key] = self.args.get(key, [])
            arg.append(value)

    def requestReceived(self, command, path, version, content):
        from string import split
        self.args = {}
        self.stack = []
        self.headers = {}

        self.method, self.uri = command, path
        self.clientproto = version
        self.content = content

        x = split(self.uri,'?')

        if len(x) == 1:
            self.path = urllib.unquote(self.uri)
        else:
            if len(x) != 2:
                log.msg("May ignore parts of this invalid URI:",repr(self.uri))
            self.path, argstring = urllib.unquote(x[0]), x[1]
            self._parse_argstring(argstring)

        self.process()

    def __repr__(self):
        return '<%s %s %s>'% (self.method, self.uri, self.clientproto)

    _host = socket.gethostbyaddr(socket.gethostname())[0]

    def process(self):
        "Process a request."
        # Log the request to a file.
        log.msg( self )

        # cache the client information, we'll need this later to be pickled and
        # sent with the request so CGIs will work remotely
        self.client = self.transport.getPeer()

        # set various default headers
        self.setHeader('server', version)
        self.setHeader('date', date_time_string())
        self.setHeader('content-type', "text/html")
        self.setHeader('connection', 'close')
        try:
            # Argument processing
            args = self.args
            if self.method == "POST":
                mfd = 'multipart/form-data'
                key, pdict = cgi.parse_header(self.getHeader('content-type'))
                if key == 'application/x-www-form-urlencoded':
                    args.update(
                        cgi.parse_qs(self.content))

                elif key == mfd:
                    args.update(
                        cgi.parse_multipart(StringIO.StringIO(self.content),
                                            pdict))
                else:
                    raise 'bad content-type'

            # Resource Identification
            self.server_port = 80
            # XXX ^^^^^^^^^^ Obviously it's not always 80.  figure it out from
            # the URI.
            self.prepath = []
            self.postpath = string.split(self.path[1:], '/')
            resrc = self.site.getResourceFor(self)
            body = resrc.render(self)
            if body == NOT_DONE_YET:
                return
            if type(body) is not types.StringType:
                body = error.ErrorPage(http.INTERNAL_SERVER_ERROR,
                    "Request did not return a string",
                    "Request: "+html.PRE(reflect.safe_repr(self))+"<BR>"+
                    "Resource: "+html.PRE(reflect.safe_repr(resrc))+"<BR>"+
                    "Value: "+html.PRE(reflect.safe_repr(body))).render(self)

        except passport.Unauthorized:
            body = "<HTML><BODY>You're not cleared for that.</BODY></HTML>"
            self.setResponseCode(http.UNAUTHORIZED)
            self.setHeader('content-type',"text/html")
        except:
            io = StringIO.StringIO()
            traceback.print_exc(file=io)
            body = "<HTML><BODY><br>web.Server Traceback \n\n" + html.PRE(io.getvalue()) + "\n\n</body></html>\n"
            log.msg( "Traceback Follows:" )
            log.msg(io.getvalue())
            self.setResponseCode(http.INTERNAL_SERVER_ERROR)
            self.setHeader('content-type',"text/html")

        self.setHeader('content-length',str(len(body)-1))
        self.write(body)
        self.finish()

    startedWriting = 0

    # The following is the public interface that people should be
    # writing to.

    def write(self, data):
        """
        Write some data as a result of an HTTP request.  The first
        time this is called, it writes out response data.
        """
        if not self.startedWriting:
            self.startedWriting = 1
            if self.clientproto != "HTTP/0.9":
                message = http.responses.get(self.code, "Unknown Status")
                self.sendStatus(self.code, message)
                for name, value in self.headers.items():
                    self.sendHeader(name, value)
                self.endHeaders()
        self.transport.write(data)

    def view_write(self, issuer, data):
        """Remote version of write; same interface.
        """
        self.write(data)

    def finish(self):
        """End the request and close the connection.
        """
        self.transport.stopConsuming()

    def view_finish(self, issuer):
        """Remote version of finish; same interface.
        """
        self.finish()

    def setHeader(self, k, v):
        """Set an outgoing HTTP header.
        """
        self.headers[string.lower(k)] = v

    def view_setHeader(self, issuer, k, v):
        """Remote version of setHeader; same interface.
        """
        self.setHeader(k, v)

    def setResponseCode(self, code):
        """Set the HTTP response code.
        """
        self.code = code

    def view_setResponseCode(self, issuer, code):
        """Remote version of setResponseCode; same interface.
        """
        self.setResponseCode(code)

    def registerProducer(self, producer, streaming):
        """Register a producer; see twisted.internet.tcp.Connection.registerProducer.
        """
        self.transport.registerProducer(producer, streaming)

    def view_registerProducer(self, issuer, producer, streaming):
        """Remote version of registerProducer; same interface.
        (requires a remote producer.)
        """
        self.registerProducer(producer, streaming)

    ### these calls remain local

    def getAllHeaders(self):
        return self.received

    session = None

    def getSession(self):
        # Session management
        if not self.session:
            cookietxt = self.getHeader("cookie")
            if cookietxt:
                cookie = string.split(cookietxt, '; ')
                vals = {}
                for cook in cookie:
                    k, v = string.split(cook, '=')
                    vals[k] = v
                sessionCookie = vals.get('TWISTED_SESSION')
                if sessionCookie:
                    try:
                        self.session = self.site.getSession(sessionCookie)
                    except KeyError:
                        pass
            # if it still hasn't been set, fix it up.
            if not self.session:
                self.session = self.site.makeSession()
                self.setHeader('Set-Cookie',
                               'TWISTED_SESSION='+self.session.uid)
        return self.session

    def getHost(self):
        return self._host

    def getClientIP(self):
        if self.client[0] == 'INET':
            return self.client[1]
        else:
            return None

    def _authorize(self):
        # Authorization, (mostly) per the RFC
        try:
            authh = self.getHeader("Authorization")
            bas, upw = string.split(authh)
            upw = base64.decodestring(upw)
            self.user, self.password = string.split(upw,':')
        except:
            self.user = self.password = ""

    def getUser(self):
        try:
            return self.user
        except:
            pass
        self._authorize()
        return self.user

    def getPassword(self):
        try:
            return self.password
        except:
            pass
        self._authorize()
        return self.password

    def getClient(self):
        if self.client[0] != 'INET':
            return None
        host = self.client[1]
        try:
            name, names, addresses = socket.gethostbyaddr(host)
        except socket.error, msg:
            return host
        names.insert(0, name)
        for name in names:
            if '.' in name:
                return name
        return names[0]


class Session:
    """A user's session with a system.

    This utility class contains no functionality, but is used to represent a
    session.
    """
    def __init__(self, uid):
        """Initialize a session with a unique ID for that session.
        """
        self.uid = uid


version = "TwistedWeb/%s" % copyright.version

class Site(protocol.Factory):
    counter = 0
    def __init__(self, resource):
        """Initialize.
        """
        self.sessions = {}
        self.resource = resource

    def _mkuid(self):
        """(internal) Generate an opaque, unique ID for a user's session.
        """
        self.counter = self.counter + 1
        return "%sx%s" % (long(time.time()*1000), self.counter)

    def makeSession(self):
        """Generate a new Session instance, and store it for future reference.
        """
        uid = self._mkuid()
        session = self.sessions[uid] = Session(uid)
        return session

    def getSession(self, uid):
        """Get a previously generated session, by its unique ID.
        This raises a KeyError if the session is not found.
        """
        return self.sessions[uid]

    def buildProtocol(self, addr):
        """Generate a request attached to this site.
        """
        r = Request()
        r.site = self
        return r

    isLeaf = 0

    def render(self, request):
        """Redirect because a Site is always a directory.
        """
        request.setHeader("location","http://%s%s/" % (
            request.getHeader("host"),
            (string.split(request.uri,'?')[0])))
        request.setResponseCode(http.MOVED_PERMANENTLY)
        return 'redirect!'

    def getChildWithDefault(self, pathEl, request):
        """Emulate a resource's getChild method.
        """
        request.site = self
        return self.resource.getChildWithDefault(pathEl, request)

    def getResourceFor(self, request):
        """Get a resource for a request.

        This iterates through the resource heirarchy, calling
        getChildWithDefault on each resource it finds for a path element,
        stopping when it hits an element where isLeaf is true.
        """
        request.site = self
        return self.resource.getChildForRequest(request)


class HTTPClient(tcp.Client):
    """A client for HTTP connections.

    My implementation is deprecated, since it doesn't use Protocols, but my
    interface should not be.  Consider me to be a class in flux.
    """
    # initial state
    handling_header = 1
    buf = ''
    bytes_received = 0
    statusCode = -1

    default_headers = {
        "user-agent": "twisted",
        "connection": "close"
    }

    def __init__(self, url, headers={}):
        """Initialize.
        """
        self.length = -1
        type, url = urllib.splittype(url)
        if type[:4] != "http":
            raise TypeError, "that's not an HTTP url, you pathetic excuse for a human being."
        host, path = urllib.splithost(url)
        host, port = urllib.splitport(host)
        if port == None:
            port = 80
        self.path = path
        self.headers = copy.copy(self.default_headers)
        self.headers.update(headers)
        self.received = {} # received headers
        tcp.Client.__init__(self, host, port)

    def onConnect(self):
        """On connect, write the request.
        """
        self.write("GET %s HTTP/1.0\r\n" % self.path)
        for k, v in self.headers.items():
            self.write("%s: %s\r\n" % (k, v))
        self.write("\r\n")

    def dataReceived(self, data):
        """Received data; parse.
        """
        if self.handling_header:
            buf = self.buf = self.buf + data
            delim = string.find(buf, '\r\n\r\n')
            if delim != -1:
                self.handling_header = 0
                headerText = buf[:delim]
                data = buf[delim+4:]
                headers = string.split(headerText,'\r\n')
                self.statusLine = headers[0]
                # deal with the status line
                eov = string.find(self.statusLine, ' ')
                self.statusVersion = self.statusLine[:eov]
                eoc = string.find(self.statusLine, ' ',eov+1)
                statusCodeTxt = self.statusLine[eov+1:eoc]
                self.statusCode = int(statusCodeTxt)
                self.statusMessage = self.statusLine[eoc+1:]
                headers = headers[1:]
                for header in headers:
                    splitAt = string.find(header, ': ')
                    if splitAt == -1:
                        log.msg( "Invalid HTTP response header: %s" % repr(header) )
                    else:
                        hkey = header[:splitAt]
                        hval = header[splitAt+2:]
                        self.received[string.lower(hkey)] = hval
                self.length = int(self.received.get('content-length', '-1'))

        if not self.handling_header:
            self.handleContent(data)
            self.bytes_received = self.bytes_received + len(data)
            if self.length != -1 and self.length <= self.bytes_received:
                self.loseConnection()

    def handleContent(self, data):
        """Override this function to handle chunks of data from the client.
        """
        log.msg( 'handling content: %s' % repr(data) )


class HTTPCallback(HTTPClient):
    """An HTTP client that will issue a callback when the server responds.

    The request has been completed.  The constructor takes a callback, which
    must have the signature callback(code, headers, data), where "code" is the
    integer response code (-1 if the request did not complete), "headers" is a
    list of HTTP headers, and "data" is the body of the page response.
    """
    data = ''
    def __init__(self, url, callback, headers={}):
        """Initialize.
        """
        HTTPClient.__init__(self, url, headers)
        self.callback = callback

    def handleContent(self, data):
        """Some content was received.
        """
        self.data = self.data + data

    def connectionLost(self):
        """The connection was lost.  Time to make my callback.
        """
        HTTPClient.connectionLost(self)
        self.callback(self.statusCode, self.received, self.data)
        del self.callback


import html
