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

"""Session Initialization Protocol.

Documented in RFC 2543.
"""

# system imports
import socket
import random
import time
import md5
import sys

# twisted imports
from twisted.python import log, util
from twisted.internet import protocol, defer, reactor
from twisted.python.components import Interface

from twisted import cred
import twisted.cred.credentials
import twisted.cred.error

# sibling imports
import basic

PORT = 5060

# SIP headers have short forms
shortHeaders = {"call-id": "i",
                "contact": "m",
                "content-encoding": "e",
                "content-length": "l",
                "content-type": "c",
                "from": "f",
                "subject": "s",
                "to": "t",
                "via": "v",
                }

longHeaders = {}
for k, v in shortHeaders.items():
    longHeaders[v] = k
del k, v

statusCodes = {
    100: "Trying",
    180: "Ringing",
    181: "Call Is Being Forwarded",
    182: "Queued",

    200: "OK",

    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Moved Temporarily",
    303: "See Other",
    305: "Use Proxy",
    380: "Alternative Service",

    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    413: "Request Entity Too Large",
    414: "Request-URI Too Large",
    415: "Unsupported Media Type",
    420: "Bad Extension",
    480: "Temporarily not available",
    481: "Call Leg/Transaction Does Not Exist",
    482: "Loop Detected",
    483: "Too Many Hops",
    484: "Address Incomplete",
    485: "Ambiguous",
    486: "Busy Here",
    
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Time-out",
    505: "SIP Version not supported",
    
    600: "Busy Everywhere",
    603: "Decline",
    604: "Does not exist anywhere",
    606: "Not Acceptable",
}

specialCases = {
    'cseq': 'CSeq',
    'call-id': 'Call-ID',
    'www-authenticate': 'WWW-Authenticate',
}

def unq(s):
    if s[0] == s[-1] == '"':
        return s[1:-1]
    return s

class Via:
    """A SIP Via header."""

    def __init__(self, host, port=PORT, transport="UDP", ttl=None, hidden=False,
                 received=None, rport=None, branch=None, maddr=None):
        self.transport = transport
        self.host = host
        self.port = port
        self.ttl = ttl
        self.hidden = hidden
        self.received = received
        self.rport = rport
        self.branch = branch
        self.maddr = maddr

    def toString(self):
        s = "SIP/2.0/%s %s:%s" % (self.transport, self.host, self.port)
        if self.hidden:
            s += ";hidden"
        for n in "ttl", "received", "branch", "maddr", "rport":
            value = getattr(self, n)
            if value != None:
                s += ";%s=%s" % (n, value)
        return s


def parseViaHeader(value):
    """Parse a Via header, returning Via class instance."""
    parts = value.split(";")
    sent, params = parts[0], parts[1:]
    protocolinfo, by = sent.split(" ", 1)
    result = {}
    pname, pversion, transport = protocolinfo.split("/")
    if pname != "SIP" or pversion != "2.0":
        raise ValueError, "wrong protocol or version: %r" % value
    result["transport"] = transport
    if ":" in by:
        host, port = by.split(":")
        result["port"] = int(port)
        result["host"] = host
    else:
        result["host"] = by
    for p in params:
        # it's the comment-striping dance!
        p = p.strip().split(" ", 1)
        if len(p) == 1:
            p, comment = p[0], ""
        else:
            p, comment = p
        if p == "hidden":
            result["hidden"] = True
            continue
        name, value = p.split("=")
        if name in ("rport", "ttl"):
            value = int(value)
        result[name] = value
    return Via(**result)


class URL:
    """A SIP URL."""

    def __init__(self, host, username=None, password=None, port=None,
                 transport=None, usertype=None, method=None,
                 ttl=None, maddr=None, tag=None, other=None, headers=None):
        self.username = username
        self.host = host
        self.password = password
        self.port = port
        self.transport = transport
        self.usertype = usertype
        self.method = method
        self.tag = tag
        self.ttl = ttl
        self.maddr = maddr
        if other == None:
            self.other = []
        else:
            self.other = other
        if headers == None:
            self.headers = {}
        else:
            self.headers = headers

    def toString(self):
        l = []; w = l.append
        w("sip:")
        if self.username != None:
            w(self.username)
            if self.password != None:
                w(":%s" % self.password)
            w("@")
        w(self.host)
        if self.port != None:
            w(":%d" % self.port)
        if self.usertype != None:
            w(";user=%s" % self.usertype)
        for n in ("transport", "ttl", "maddr", "method", "tag"):
            v = getattr(self, n)
            if v != None:
                w(";%s=%s" % (n, v))
        for v in self.other:
            w(";%s" % v)
        if self.headers:
            w("?")
            w("&".join([("%s=%s" % (specialCases.get(h) or h.capitalize(), v)) for (h, v) in self.headers.items()]))
        return "".join(l)

    def __str__(self):
        return self.toString()
    
    def __repr__(self):
        return '<URL %s:%s@%s:%r/%s>' % (self.username, self.password, self.host, self.port, self.transport)


def parseURL(url):
    """Return string into URL object.

    URIs are of of form 'sip:user@example.com'.
    """
    d = {}
    if not url.startswith("sip:"):
        raise ValueError("unsupported scheme: " + url[:4])
    parts = url[4:].split(";")
    userdomain, params = parts[0], parts[1:]
    udparts = userdomain.split("@", 1)
    if len(udparts) == 2:
        userpass, hostport = udparts
        upparts = userpass.split(":", 1)
        if len(upparts) == 1:
            d["username"] = upparts[0]
        else:
            d["username"] = upparts[0]
            d["password"] = upparts[1]
    else:
        hostport = udparts[0]
    hpparts = hostport.split(":", 1)
    if len(hpparts) == 1:
        d["host"] = hpparts[0]
    else:
        d["host"] = hpparts[0]
        d["port"] = int(hpparts[1])
    for p in params:
        if p == params[-1] and "?" in p:
            d["headers"] = h = {}
            p, headers = p.split("?", 1)
            for header in headers.split("&"):
                k, v = header.split("=")
                h[k] = v
        nv = p.split("=", 1)
        if len(nv) == 1:
            d.setdefault("other", []).append(p)
            continue
        name, value = nv
        if name == "user":
            d["usertype"] = value
        elif name in ("transport", "ttl", "maddr", "method", "tag"):
            if name == "ttl":
                value = int(value)
            d[name] = value
        else:
            d.setdefault("other", []).append(p)
    return URL(**d)


def cleanRequestURL(url):
    """Clean a URL from a Request line."""
    url.transport = None
    url.maddr = None
    url.ttl = None
    url.headers = {}


def parseAddress(address, clean=0):
    """Return (name, uri, params) for From/To/Contact header.

    @param clean: remove unnecessary info, usually for From and To headers.
    """
    address = address.strip()
    # simple 'sip:foo' case
    if address.startswith("sip:"):
        return "", parseURL(address), {}
    params = {}
    name, url = address.split("<", 1)
    name = name.strip()
    if name.startswith('"'):
        name = name[1:]
    if name.endswith('"'):
        name = name[:-1]
    url, paramstring = url.split(">", 1)
    url = parseURL(url)
    paramstring = paramstring.strip()
    if paramstring:
        for l in paramstring.split(";"):
            if not l:
                continue
            k, v = l.split("=")
            params[k] = v
    if clean:
        # rfc 2543 6.21
        url.ttl = None
        url.headers = {}
        url.transport = None
        url.maddr = None
    return name, url, params


class SIPError(Exception):
    def __init__(self, code, phrase=None):
        if phrase is None:
            phrase = statusCodes[code]
        Exception.__init__(self, "SIP error (%d): %s" % (code, phrase))
        self.code = code
        self.phrase = phrase


class RegistrationError(SIPError):
    """Registration was not possible."""


class Message:
    """A SIP message."""

    length = None
    
    def __init__(self):
        self.headers = util.OrderedDict() # map name to list of values
        self.body = ""
        self.finished = 0
    
    def addHeader(self, name, value):
        name = name.lower()
        name = longHeaders.get(name, name)
        if name == "content-length":
            self.length = int(value)
        self.headers.setdefault(name,[]).append(value)

    def bodyDataReceived(self, data):
        self.body += data
    
    def creationFinished(self):
        if (self.length != None) and (self.length != len(self.body)):
            raise ValueError, "wrong body length"
        self.finished = 1

    def toString(self):
        s = "%s\r\n" % self._getHeaderLine()
        for n, vs in self.headers.items():
            for v in vs:
                s += "%s: %s\r\n" % (specialCases.get(n) or n.capitalize(), v)
        s += "\r\n"
        s += self.body
        return s

    def _getHeaderLine(self):
        raise NotImplementedError


class Request(Message):
    """A Request for a URI"""


    def __init__(self, method, uri, version="SIP/2.0"):
        Message.__init__(self)
        self.method = method
        if isinstance(uri, URL):
            self.uri = uri
        else:
            self.uri = parseURL(uri)
            cleanRequestURL(self.uri)
    
    def __repr__(self):
        return "<SIP Request %d:%s %s>" % (id(self), self.method, self.uri.toString())

    def _getHeaderLine(self):
        return "%s %s SIP/2.0" % (self.method, self.uri.toString())


class Response(Message):
    """A Response to a URI Request"""

    def __init__(self, code, phrase=None, version="SIP/2.0"):
        Message.__init__(self)
        self.code = code
        if phrase == None:
            phrase = statusCodes[code]
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
    
    debug = 0
    
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
            raise RuntimeError, "this should never happen"
    
    def dataReceived(self, data):
        try:
            basic.LineReceiver.dataReceived(self, data)
        except:
            log.err()
            self.invalidMessage()
    
    def handleFirstLine(self, line):
        """Expected to create self.message."""
        raise NotImplementedError

    def lineLengthExceeded(self, line):
        self.invalidMessage()
    
    def lineReceived(self, line):
        if self.state == "firstline":
            while line.startswith("\n") or line.startswith("\r"):
                line = line[1:]
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


class Base(protocol.DatagramProtocol):
    """Base class for SIP clients and servers."""
    
    PORT = PORT
    debug = False
    
    def __init__(self):
        self.messages = []
        self.parser = MessagesParser(self.addMessage)

    def addMessage(self, msg):
        self.messages.append(msg)

    def datagramReceived(self, data, addr):
        self.parser.dataReceived(data)
        self.parser.dataDone()
        for m in self.messages:
            if self.debug:
                log.msg("Received %r from %r" % (m, addr))
            self._fixupNAT(m, addr)
            if isinstance(m, Request):
                self.handle_request(m, addr)
            else:
                self.handle_response(m, addr)
        self.messages[:] = []

    def _fixupNAT(self, message, (srcHost, srcPort)):
        # RFC 2543 6.40.2
        senderVia = parseViaHeader(message.headers["via"][0])
        if senderVia.host != srcHost:
            senderVia.received = srcHost
        if senderVia.port != srcPort:
            senderVia.rport = srcPort
        if senderVia.received is not None or senderVia.rport is not None:
            message.headers["via"][0] = senderVia.toString()

    def deliverResponse(self, responseMessage):
        """Deliver response.

        Destination is based on topmost Via header."""
        destVia = parseViaHeader(responseMessage.headers["via"][0])
        # XXX we don't do multicast yet
        host = destVia.received or destVia.host
        port = destVia.rport or destVia.port or self.PORT
        destAddr = URL(host=host, port=port)
        self.sendMessage(destAddr, responseMessage)

    def responseFromRequest(self, code, request):
        """Create a response to a request message."""
        response = Response(code)
        for name in ("via", "to", "from", "call-id", "cseq"):
            response.headers[name] = request.headers.get(name, [])[:]
        return response

    def sendMessage(self, destURL, message):
        """Send a message.

        @param dest: C{URL}. This should be a *physical* URL, not a logical one.
        @param message: The message to send.
        """
        log.msg("Sending %s to %s" % (message, destURL))
        if destURL.transport not in ("udp", None):
            raise RuntimeError, "only UDP currently supported"
        if self.debug:
            log.msg("Sending %r to %r" % (message.toString(), destURL))
        self.transport.write(message.toString(), (destURL.host, destURL.port or self.PORT))

    def handle_request(self, message, addr):
        """Override to define behavior for requests received

        @type message: C{Message}
        @type addr: C{tuple}
        """
        raise NotImplementedError

    def handle_response(self, message, addr):
        """Override to define behavior for responses received.
        
        @type message: C{Message}
        @type addr: C{tuple}
        """
        raise NotImplementedError


class IContact(Interface):
    """A user of a registrar or proxy"""


class IContact(Interface):
    """A user of a registrar or proxy"""

class IRegistry(Interface):
    """Allows registration of logical->physical URL mapping."""

    def registerAddress(self, domainURL, logicalURL, physicalURL):
        """Register the physical address of a logical URL.

        @return: Deferred of (secondsToExpiry, contact URL) or failure with RegistrationError.
        """

    def getRegistrationInfo(self, logicalURL):
        """Get registration info for logical URL.

        @return: Deferred of (secondsToExpiry, contact URL) or failure with LookupError.
        """


class ILocator(Interface):
    """Allow looking up physical address for logical URL."""

    def getAddress(self, logicalURL):
        """Return physical URL of server for logical URL of user.

        @param userURL: a logical C{URL}.
        @return: Deferred which becomes URL or fails with LookupError.
        """


class Proxy(Base):
    """SIP proxy."""
    
    PORT = PORT

    locator = None # object implementing ILocator
    
    def __init__(self, host=None, port=PORT):
        """Create new instance.

        @param host: our hostname/IP as set in Via headers.
        @param port: our port as set in Via headers.
        """
        self.host = host or socket.getfqdn()
        self.port = port
        Base.__init__(self)
        
    def getVia(self):
        """Return value of Via header for this proxy."""
        return Via(host=self.host, port=self.port)

    def handle_request(self, message, addr):
        f = getattr(self, "handle_%s_request" % message.method, None)
        if f is None:
            f = self.handle_request_default
        try:
            d = f(message, addr)
        except SIPError, e:
            self.deliverResponse(self.responseFromRequest(e.code, message))
        except:
            log.err()
            self.deliverResponse(self.responseFromRequest(500, message))
        else:
            if d is not None:
                d.addErrback(lambda e:
                    self.deliverResponse(self.responseFromRequest(e.code, message))
                )
        
    def handle_request_default(self, message, (srcHost, srcPort)):
        """Default request handler.
        
        Default behaviour for OPTIONS and unknown methods for proxies
        is to forward message on to the client.

        Since at the moment we are stateless proxy, thats basically
        everything.
        """
        viaHeader = self.getVia()
        if viaHeader.toString() in message.headers["via"]:
            # must be a loop, so drop message
            log.msg("Dropping looped message.")
            return

        message.headers["via"].insert(0, viaHeader.toString())
        name, uri, tags = parseAddress(message.headers["to"][0], clean=1)
        d = self.locator.getAddress(uri)
        d.addCallback(self.sendMessage, message)
        d.addErrback(self._cantForwardRequest, message)
    
    def _cantForwardRequest(self, error, message):
        error.trap(LookupError)
        del message.headers["via"][0] # this'll be us
        self.deliverResponse(self.responseFromRequest(404, message))
    
    def deliverResponse(self, responseMessage):
        """Deliver response.

        Destination is based on topmost Via header."""
        destVia = parseViaHeader(responseMessage.headers["via"][0])
        # XXX we don't do multicast yet
        host = destVia.received or destVia.host
        port = destVia.rport or destVia.port or self.PORT
        destAddr = URL(host=host, port=port)
        self.sendMessage(destAddr, responseMessage)

    def responseFromRequest(self, code, request):
        """Create a response to a request message."""
        response = Response(code)
        for name in ("via", "to", "from", "call-id", "cseq"):
            response.headers[name] = request.headers.get(name, [])[:]
        return response
    
    def handle_response(self, message, addr):
        """Default response handler."""
        v = parseViaHeader(message.headers["via"][0])
        if (v.host, v.port) != (self.host, self.port):
            # we got a message not intended for us?
            # XXX note this check breaks if we have multiple external IPs
            # yay for suck protocols
            log.msg("Dropping incorrectly addressed message")
            return
        del message.headers["via"][0]
        if not message.headers["via"]:
            # this message is addressed to us
            self.gotResponse(message, addr)
            return
        self.deliverResponse(message)
    
    def gotResponse(self, message, addr):
        """Called with responses that are addressed at this server."""
        pass

class IAuthorizer(Interface):
    def getChallenge(self, peer):
        """Generate a challenge the client may respond to.
        
        @type peer: C{tuple}
        @type peer: The client's address
        
        @rtype: C{str}
        @return: The challenge string
        """
    
    def decode(self, response):
        """Create a credentials object from the given response.
        
        @type response: C{str}
        """
 
class BasicAuthorizer:
    __implements__ = (IAuthorizer,)
    
    def getChallenge(self, peer):
        return None
    
    def decode(self, response):
        # At least one SIP client improperly pads its Base64 encoded messages
        for i in range(3):
            try:
                creds = (response + ('=' * i)).decode('base64')
            except:
                pass
            else:
                break
        else:
            # Totally bogus
            raise SIPError(400)
        p = creds.split(':', 1)
        if len(p) == 2:
            return cred.credentials.UsernamePassword(*p)
        raise SIPError(400)

class DigestedCredentials(cred.credentials.UsernameHashedPassword):
    """Yet Another Simple Digest-MD5 authentication scheme"""
    
    def __init__(self, username, fields):
        self.username = username
        self.fields = fields
    
    def checkPassword(self, password):
        H = lambda x: md5.md5(x).digest()
        KD = lambda s, d: H(s + ":" + d)

        method = 'REGISTER'
        response = self.fields.get('response')
        uri = self.fields.get('uri')
        nonce = self.fields.get('nonce', '')

        user, domain = self.username.split('@', 1)
        if uri is None:
            uri = 'sip:' + domain

        print 'user=%(user)s\ndomain=%(domain)s\nuri=%(uri)s' % locals()
        print 'method=%(method)s\nresponse=%(response)s\nnonce=%(nonce)s' % locals()

        A1 = H(user + ':' + domain + ':' + password).encode('hex')
        A2 = H(method + ':' + uri).encode('hex')
        expected = KD(A1, nonce + ":" + A2).encode('hex')
        
        print 'A1=%(A1)s\nA2=%(A2)s\nexpected=%(expected)s' % locals()

        return expected == response

class DigestAuthorizer:
    CHALLENGE_LIFETIME = 15
    
    __implements__ = (IAuthorizer,)
    
    def __init__(self):
        self.outstanding = {}
    
    def getChallenge(self, peer):
        c = tuple([random.randrange(sys.maxint) for _ in range(3)])
        c = '%d%d%d' % c
        self.outstanding[c] = True
        return ','.join((
            'nonce="%s"' % 'abcdefg', # c.encode('base64').strip(),
            'opaque="%s"' % str(random.randrange(sys.maxint)),
            'qop-options="auth"',
        ))
        
    def decode(self, response):
        response = ' '.join(response.splitlines())
        parts = response.split(',')
        auth = dict([(k, unq(v)) for (k, v) in [p.split('=', 1) for p in parts]])
        try:
            username = auth['username']
        except KeyError:
            raise SIPError(401)
        try:
            return DigestedCredentials(username, auth)
        except:
            raise SIPError(400)

class RegisterProxy(Proxy):
    """A proxy that allows registration for a specific domain.

    Unregistered users won't be handled.
    """

    portal = None

    registry = None # should implement IRegistry

    authorizers = {
        'basic': BasicAuthorizer(),
        'digest': DigestAuthorizer(),
    }
    
    def __init__(self, *args, **kw):
        Proxy.__init__(self, *args, **kw)
        self.liveChallenges = {}
        
    def handle_REGISTER_request(self, message, (host, port)):
        """Handle a registration request.

        Currently registration is not proxied.
        """
        if self.portal is None:
            # There is no portal.  Let anyone in.
            self.register(message, host, port)
        else:
            # There is a portal.  Check for credentials.
            if not message.headers.has_key("authorization"):
                return self.unauthorized(message, host, port)
            else:
                return self.login(message, host, port)
    
    def unauthorized(self, message, host, port):
        m = self.responseFromRequest(401, message)
        for (scheme, auth) in self.authorizers.iteritems():
            chal = auth.getChallenge((host, port))
            if chal is None:
                value = '%s realm="%s"' % (scheme.title(), self.host)
            else:
                value = '%s %s,realm="%s"' % (scheme.title(), chal, self.host)
            m.headers.setdefault('www-authenticate', []).append(value)
        self.deliverResponse(m)

    def login(self, message, host, port):
        parts = message.headers['authorization'][0].split(None, 1)
        a = self.authorizers.get(parts[0].lower())
        if a:
            try:
                c = a.decode(parts[1])
            except SIPError:
                raise
            except:
                log.err()
                self.deliverResponse(self.responseFromRequest(500, message))
            else:
                c.username += '@' + self.host
                self.portal.login(c, None, IContact
                    ).addCallback(self._cbLogin, message, host, port
                    ).addErrback(self._ebLogin, message, host, port
                    ).addErrback(log.err
                    )
        else:
            self.deliverResponse(self.responseFromRequest(501, message))

    def _cbLogin(self, (i, a, l), message, host, port):
        # It's stateless, matey.  What a joke.
        self.register(message, host, port)
    
    def _ebLogin(self, failure, message, host, port):
        failure.trap(cred.error.UnauthorizedLogin)
        self.unauthorized(message, host, port)

    def register(self, message, host, port):
        """Allow all users to register"""
        name, toURL, params = parseAddress(message.headers["to"][0], clean=1)
        if message.headers.has_key("contact"):
            contact = message.headers["contact"][0]
            name, contactURL, params = parseAddress(contact)
            d = self.registry.registerAddress(message.uri, toURL, contactURL)
        else:
            d = self.registry.getRegistrationInfo(toURL)
        d.addCallbacks(self._registeredResult, self._registerError, callbackArgs=(message,))
        
    def _registeredResult(self, (expirySeconds, contactURL), message):
        response = self.responseFromRequest(200, message)
        if contactURL != None:
            response.addHeader("contact", contactURL.toString())
            response.addHeader("expires", "%d" % expirySeconds)
        response.addHeader("content-length", "0")
        self.deliverResponse(response)

    def _registerError(self, error):
        error.trap(RegistrationError, LookupError)
        # XXX return error message, and alter tests to deal with
        # this, currently tests assume no message sent on failure


class InMemoryRegistry:
    """A simplistic registry for a specific domain."""

    __implements__ = IRegistry, ILocator
    
    def __init__(self, domain):
        self.domain = domain # the domain we handle registration for
        self.users = {} # map username to (IDelayedCall for expiry, address URI)

    def getAddress(self, userURI):
        if userURI.host != self.domain:
            return defer.fail(LookupError("unknown domain"))
        if self.users.has_key(userURI.username):
            dc, url = self.users[userURI.username]
            return defer.succeed(url)
        else:
            return defer.fail(LookupError("no such user"))

    def getRegistrationInfo(self, userURI):
        if userURI.host != self.domain:
            return defer.fail(LookupError("unknown domain"))
        if self.users.has_key(userURI.username):
            dc, url = self.users[userURI.username]
            return defer.succeed((int(dc.getTime() - time.time()), url))
        else:
            return defer.fail(LookupError("no such user"))
        
    def _expireRegistration(self, username):
        try:
            del self.users[username]
        except KeyError:
            pass

    def registerAddress(self, domainURL, logicalURL, physicalURL):
        if domainURL.host != self.domain:
            log.msg("Registration for domain we don't handle.")
            return defer.fail(RegistrationError(404))
        if logicalURL.host != self.domain:
            log.msg("Registration for domain we don't handle.")
            return defer.fail(RegistrationError(404))
        # XXX we should check for expires header and in URI, and allow
        # unregistration
        if self.users.has_key(logicalURL.username):
            dc, old = self.users[logicalURL.username]
            dc.reset(3600)
        else:
            dc = reactor.callLater(3600, self._expireRegistration, logicalURL.username)
        log.msg("Registered %s at %s" % (logicalURL.toString(), physicalURL.toString()))
        self.users[logicalURL.username] = (dc, physicalURL)
        return defer.succeed((int(dc.getTime() - time.time()), physicalURL))


if __name__ == '__main__':
    import sys
    log.startLogging(sys.stdout)
    registrar = RegisterProxy(host="192.168.1.1")
    registrar.portal = 5
    registry = InMemoryRegistry("192.168.1.1")
    registrar.registry = registry
    registry.locator = registry
    reactor.listenUDP(PORT, registrar)
    reactor.run()
