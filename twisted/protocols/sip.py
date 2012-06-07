# -*- test-case-name: twisted.test.test_sip -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Session Initialization Protocol.

Documented in RFC 2543.
[Superceded by 3261]


This module contains a deprecated implementation of HTTP Digest authentication.
See L{twisted.cred.credentials} and L{twisted.cred._digest} for its new home.
"""

# system imports
import socket, time, sys, random, warnings
from zope.interface import implements, Interface

# twisted imports
from twisted.python import log, util
from twisted.python.deprecate import deprecated
from twisted.python.versions import Version
from twisted.python.hashlib import md5
from twisted.internet import protocol, defer, reactor

from twisted import cred
import twisted.cred.error
from twisted.cred.credentials import UsernameHashedPassword, UsernamePassword


# sibling imports
from twisted.protocols import basic

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
    183: "Session Progress",

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
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict", # Not in RFC3261
    410: "Gone",
    411: "Length Required", # Not in RFC3261
    413: "Request Entity Too Large",
    414: "Request-URI Too Large",
    415: "Unsupported Media Type",
    416: "Unsupported URI Scheme",
    420: "Bad Extension",
    421: "Extension Required",
    423: "Interval Too Brief",
    480: "Temporarily Unavailable",
    481: "Call/Transaction Does Not Exist",
    482: "Loop Detected",
    483: "Too Many Hops",
    484: "Address Incomplete",
    485: "Ambiguous",
    486: "Busy Here",
    487: "Request Terminated",
    488: "Not Acceptable Here",
    491: "Request Pending",
    493: "Undecipherable",

    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway", # no donut
    503: "Service Unavailable",
    504: "Server Time-out",
    505: "SIP Version not supported",
    513: "Message Too Large",

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


def dashCapitalize(s):
    ''' Capitalize a string, making sure to treat - as a word seperator '''
    return '-'.join([ x.capitalize() for x in s.split('-')])

def unq(s):
    if s[0] == s[-1] == '"':
        return s[1:-1]
    return s

def DigestCalcHA1(
    pszAlg,
    pszUserName,
    pszRealm,
    pszPassword,
    pszNonce,
    pszCNonce,
):
    m = md5()
    m.update(pszUserName)
    m.update(":")
    m.update(pszRealm)
    m.update(":")
    m.update(pszPassword)
    HA1 = m.digest()
    if pszAlg == "md5-sess":
        m = md5()
        m.update(HA1)
        m.update(":")
        m.update(pszNonce)
        m.update(":")
        m.update(pszCNonce)
        HA1 = m.digest()
    return HA1.encode('hex')


DigestCalcHA1 = deprecated(Version("Twisted", 9, 0, 0))(DigestCalcHA1)

def DigestCalcResponse(
    HA1,
    pszNonce,
    pszNonceCount,
    pszCNonce,
    pszQop,
    pszMethod,
    pszDigestUri,
    pszHEntity,
):
    m = md5()
    m.update(pszMethod)
    m.update(":")
    m.update(pszDigestUri)
    if pszQop == "auth-int":
        m.update(":")
        m.update(pszHEntity)
    HA2 = m.digest().encode('hex')

    m = md5()
    m.update(HA1)
    m.update(":")
    m.update(pszNonce)
    m.update(":")
    if pszNonceCount and pszCNonce: # pszQop:
        m.update(pszNonceCount)
        m.update(":")
        m.update(pszCNonce)
        m.update(":")
        m.update(pszQop)
        m.update(":")
    m.update(HA2)
    hash = m.digest().encode('hex')
    return hash


DigestCalcResponse = deprecated(Version("Twisted", 9, 0, 0))(DigestCalcResponse)

_absent = object()

class Via(object):
    """
    A L{Via} is a SIP Via header, representing a segment of the path taken by
    the request.

    See RFC 3261, sections 8.1.1.7, 18.2.2, and 20.42.

    @ivar transport: Network protocol used for this leg. (Probably either "TCP"
    or "UDP".)
    @type transport: C{str}
    @ivar branch: Unique identifier for this request.
    @type branch: C{str}
    @ivar host: Hostname or IP for this leg.
    @type host: C{str}
    @ivar port: Port used for this leg.
    @type port C{int}, or None.
    @ivar rportRequested: Whether to request RFC 3581 client processing or not.
    @type rportRequested: C{bool}
    @ivar rportValue: Servers wishing to honor requests for RFC 3581 processing
    should set this parameter to the source port the request was received
    from.
    @type rportValue: C{int}, or None.

    @ivar ttl: Time-to-live for requests on multicast paths.
    @type ttl: C{int}, or None.
    @ivar maddr: The destination multicast address, if any.
    @type maddr: C{str}, or None.
    @ivar hidden: Obsolete in SIP 2.0.
    @type hidden: C{bool}
    @ivar otherParams: Any other parameters in the header.
    @type otherParams: C{dict}
    """

    def __init__(self, host, port=PORT, transport="UDP", ttl=None,
                 hidden=False, received=None, rport=_absent, branch=None,
                 maddr=None, **kw):
        """
        Set parameters of this Via header. All arguments correspond to
        attributes of the same name.

        To maintain compatibility with old SIP
        code, the 'rport' argument is used to determine the values of
        C{rportRequested} and C{rportValue}. If None, C{rportRequested} is set
        to True. (The deprecated method for doing this is to pass True.) If an
        integer, C{rportValue} is set to the given value.

        Any arguments not explicitly named here are collected into the
        C{otherParams} dict.
        """
        self.transport = transport
        self.host = host
        self.port = port
        self.ttl = ttl
        self.hidden = hidden
        self.received = received
        if rport is True:
            warnings.warn(
                "rport=True is deprecated since Twisted 9.0.",
                DeprecationWarning,
                stacklevel=2)
            self.rportValue = None
            self.rportRequested = True
        elif rport is None:
            self.rportValue = None
            self.rportRequested = True
        elif rport is _absent:
            self.rportValue = None
            self.rportRequested = False
        else:
            self.rportValue = rport
            self.rportRequested = False

        self.branch = branch
        self.maddr = maddr
        self.otherParams = kw


    def _getrport(self):
        """
        Returns the rport value expected by the old SIP code.
        """
        if self.rportRequested == True:
            return True
        elif self.rportValue is not None:
            return self.rportValue
        else:
            return None


    def _setrport(self, newRPort):
        """
        L{Base._fixupNAT} sets C{rport} directly, so this method sets
        C{rportValue} based on that.

        @param newRPort: The new rport value.
        @type newRPort: C{int}
        """
        self.rportValue = newRPort
        self.rportRequested = False


    rport = property(_getrport, _setrport)

    def toString(self):
        """
        Serialize this header for use in a request or response.
        """
        s = "SIP/2.0/%s %s:%s" % (self.transport, self.host, self.port)
        if self.hidden:
            s += ";hidden"
        for n in "ttl", "branch", "maddr", "received":
            value = getattr(self, n)
            if value is not None:
                s += ";%s=%s" % (n, value)
        if self.rportRequested:
            s += ";rport"
        elif self.rportValue is not None:
            s += ";rport=%s" % (self.rport,)

        etc = self.otherParams.items()
        etc.sort()
        for k, v in etc:
            if v is None:
                s += ";" + k
            else:
                s += ";%s=%s" % (k, v)
        return s


def parseViaHeader(value):
    """
    Parse a Via header.

    @return: The parsed version of this header.
    @rtype: L{Via}
    """
    parts = value.split(";")
    sent, params = parts[0], parts[1:]
    protocolinfo, by = sent.split(" ", 1)
    by = by.strip()
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
        parts = p.split("=", 1)
        if len(parts) == 1:
            name, value = parts[0], None
        else:
            name, value = parts
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
            w("&".join([("%s=%s" % (specialCases.get(h) or dashCapitalize(h), v)) for (h, v) in self.headers.items()]))
        return "".join(l)

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return '<URL %s:%s@%s:%r/%s>' % (self.username, self.password, self.host, self.port, self.transport)


def parseURL(url, host=None, port=None):
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
    if host != None:
        d["host"] = host
    if port != None:
        d["port"] = port
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


def parseAddress(address, host=None, port=None, clean=0):
    """Return (name, uri, params) for From/To/Contact header.

    @param clean: remove unnecessary info, usually for From and To headers.
    """
    address = address.strip()
    # simple 'sip:foo' case
    if address.startswith("sip:"):
        return "", parseURL(address, host=host, port=port), {}
    params = {}
    name, url = address.split("<", 1)
    name = name.strip()
    if name.startswith('"'):
        name = name[1:]
    if name.endswith('"'):
        name = name[:-1]
    url, paramstring = url.split(">", 1)
    url = parseURL(url, host=host, port=port)
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
                s += "%s: %s\r\n" % (specialCases.get(n) or dashCapitalize(n), v)
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
        self.header = None
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
            # multiline header
            if line.startswith(" ") or line.startswith("\t"):
                name, value = self.header
                self.header = name, (value + line.lstrip())
            else:
                # new header
                if self.header:
                    self.message.addHeader(*self.header)
                    self.header = None
                try:
                    name, value = line.split(":", 1)
                except ValueError:
                    self.invalidMessage()
                    return
                self.header = name, value.lstrip()
                # XXX we assume content-length won't be multiline
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
            if self.header:
                self.message.addHeader(*self.header)
                self.header = None
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
            self._fixupNAT(m, addr)
            if self.debug:
                log.msg("Received %r from %r" % (m.toString(), addr))
            if isinstance(m, Request):
                self.handle_request(m, addr)
            else:
                self.handle_response(m, addr)
        self.messages[:] = []

    def _fixupNAT(self, message, (srcHost, srcPort)):
        # RFC 2543 6.40.2,
        senderVia = parseViaHeader(message.headers["via"][0])
        if senderVia.host != srcHost:
            senderVia.received = srcHost
            if senderVia.port != srcPort:
                senderVia.rport = srcPort
            message.headers["via"][0] = senderVia.toString()
        elif senderVia.rport == True:
            senderVia.received = srcHost
            senderVia.rport = srcPort
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

        @param destURL: C{URL}. This should be a *physical* URL, not a logical one.
        @param message: The message to send.
        """
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


class Registration:
    def __init__(self, secondsToExpiry, contactURL):
        self.secondsToExpiry = secondsToExpiry
        self.contactURL = contactURL

class IRegistry(Interface):
    """Allows registration of logical->physical URL mapping."""

    def registerAddress(domainURL, logicalURL, physicalURL):
        """Register the physical address of a logical URL.

        @return: Deferred of C{Registration} or failure with RegistrationError.
        """

    def unregisterAddress(domainURL, logicalURL, physicalURL):
        """Unregister the physical address of a logical URL.

        @return: Deferred of C{Registration} or failure with RegistrationError.
        """

    def getRegistrationInfo(logicalURL):
        """Get registration info for logical URL.

        @return: Deferred of C{Registration} object or failure of LookupError.
        """


class ILocator(Interface):
    """Allow looking up physical address for logical URL."""

    def getAddress(logicalURL):
        """Return physical URL of server for logical URL of user.

        @param logicalURL: a logical C{URL}.
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
        # send immediate 100/trying message before processing
        #self.deliverResponse(self.responseFromRequest(100, message))
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
        def _mungContactHeader(uri, message):
            message.headers['contact'][0] = uri.toString()
            return self.sendMessage(uri, message)

        viaHeader = self.getVia()
        if viaHeader.toString() in message.headers["via"]:
            # must be a loop, so drop message
            log.msg("Dropping looped message.")
            return

        message.headers["via"].insert(0, viaHeader.toString())
        name, uri, tags = parseAddress(message.headers["to"][0], clean=1)

        # this is broken and needs refactoring to use cred
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
    def getChallenge(peer):
        """Generate a challenge the client may respond to.

        @type peer: C{tuple}
        @param peer: The client's address

        @rtype: C{str}
        @return: The challenge string
        """

    def decode(response):
        """Create a credentials object from the given response.

        @type response: C{str}
        """

class BasicAuthorizer:
    """Authorizer for insecure Basic (base64-encoded plaintext) authentication.

    This form of authentication is broken and insecure.  Do not use it.
    """

    implements(IAuthorizer)

    def __init__(self):
        """
        This method exists solely to issue a deprecation warning.
        """
        warnings.warn(
            "twisted.protocols.sip.BasicAuthorizer was deprecated "
            "in Twisted 9.0.0",
            category=DeprecationWarning,
            stacklevel=2)


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
            return UsernamePassword(*p)
        raise SIPError(400)



class DigestedCredentials(UsernameHashedPassword):
    """Yet Another Simple Digest-MD5 authentication scheme"""

    def __init__(self, username, fields, challenges):
        warnings.warn(
            "twisted.protocols.sip.DigestedCredentials was deprecated "
            "in Twisted 9.0.0",
            category=DeprecationWarning,
            stacklevel=2)
        self.username = username
        self.fields = fields
        self.challenges = challenges

    def checkPassword(self, password):
        method = 'REGISTER'
        response = self.fields.get('response')
        uri = self.fields.get('uri')
        nonce = self.fields.get('nonce')
        cnonce = self.fields.get('cnonce')
        nc = self.fields.get('nc')
        algo = self.fields.get('algorithm', 'MD5')
        qop = self.fields.get('qop-options', 'auth')
        opaque = self.fields.get('opaque')

        if opaque not in self.challenges:
            return False
        del self.challenges[opaque]

        user, domain = self.username.split('@', 1)
        if uri is None:
            uri = 'sip:' + domain

        expected = DigestCalcResponse(
            DigestCalcHA1(algo, user, domain, password, nonce, cnonce),
            nonce, nc, cnonce, qop, method, uri, None,
        )

        return expected == response

class DigestAuthorizer:
    CHALLENGE_LIFETIME = 15

    implements(IAuthorizer)

    def __init__(self):
        warnings.warn(
            "twisted.protocols.sip.DigestAuthorizer was deprecated "
            "in Twisted 9.0.0",
            category=DeprecationWarning,
            stacklevel=2)

        self.outstanding = {}



    def generateNonce(self):
        c = tuple([random.randrange(sys.maxint) for _ in range(3)])
        c = '%d%d%d' % c
        return c

    def generateOpaque(self):
        return str(random.randrange(sys.maxint))

    def getChallenge(self, peer):
        c = self.generateNonce()
        o = self.generateOpaque()
        self.outstanding[o] = c
        return ','.join((
            'nonce="%s"' % c,
            'opaque="%s"' % o,
            'qop-options="auth"',
            'algorithm="MD5"',
        ))

    def decode(self, response):
        response = ' '.join(response.splitlines())
        parts = response.split(',')
        auth = dict([(k.strip(), unq(v.strip())) for (k, v) in [p.split('=', 1) for p in parts]])
        try:
            username = auth['username']
        except KeyError:
            raise SIPError(401)
        try:
            return DigestedCredentials(username, auth, self.outstanding)
        except:
            raise SIPError(400)


class RegisterProxy(Proxy):
    """A proxy that allows registration for a specific domain.

    Unregistered users won't be handled.
    """

    portal = None

    registry = None # should implement IRegistry

    authorizers = {}

    def __init__(self, *args, **kw):
        Proxy.__init__(self, *args, **kw)
        self.liveChallenges = {}
        if "digest" not in self.authorizers:
            self.authorizers["digest"] = DigestAuthorizer()

    def handle_ACK_request(self, message, (host, port)):
        # XXX
        # ACKs are a client's way of indicating they got the last message
        # Responding to them is not a good idea.
        # However, we should keep track of terminal messages and re-transmit
        # if no ACK is received.
        pass

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
        contact = None
        if message.headers.has_key("contact"):
            contact = message.headers["contact"][0]

        if message.headers.get("expires", [None])[0] == "0":
            self.unregister(message, toURL, contact)
        else:
            # XXX Check expires on appropriate URL, and pass it to registry
            # instead of having registry hardcode it.
            if contact is not None:
                name, contactURL, params = parseAddress(contact, host=host, port=port)
                d = self.registry.registerAddress(message.uri, toURL, contactURL)
            else:
                d = self.registry.getRegistrationInfo(toURL)
            d.addCallbacks(self._cbRegister, self._ebRegister,
                callbackArgs=(message,),
                errbackArgs=(message,)
            )

    def _cbRegister(self, registration, message):
        response = self.responseFromRequest(200, message)
        if registration.contactURL != None:
            response.addHeader("contact", registration.contactURL.toString())
            response.addHeader("expires", "%d" % registration.secondsToExpiry)
        response.addHeader("content-length", "0")
        self.deliverResponse(response)

    def _ebRegister(self, error, message):
        error.trap(RegistrationError, LookupError)
        # XXX return error message, and alter tests to deal with
        # this, currently tests assume no message sent on failure

    def unregister(self, message, toURL, contact):
        try:
            expires = int(message.headers["expires"][0])
        except ValueError:
            self.deliverResponse(self.responseFromRequest(400, message))
        else:
            if expires == 0:
                if contact == "*":
                    contactURL = "*"
                else:
                    name, contactURL, params = parseAddress(contact)
                d = self.registry.unregisterAddress(message.uri, toURL, contactURL)
                d.addCallback(self._cbUnregister, message
                    ).addErrback(self._ebUnregister, message
                    )

    def _cbUnregister(self, registration, message):
        msg = self.responseFromRequest(200, message)
        msg.headers.setdefault('contact', []).append(registration.contactURL.toString())
        msg.addHeader("expires", "0")
        self.deliverResponse(msg)

    def _ebUnregister(self, registration, message):
        pass


class InMemoryRegistry:
    """A simplistic registry for a specific domain."""

    implements(IRegistry, ILocator)

    def __init__(self, domain):
        self.domain = domain # the domain we handle registration for
        self.users = {} # map username to (IDelayedCall for expiry, address URI)

    def getAddress(self, userURI):
        if userURI.host != self.domain:
            return defer.fail(LookupError("unknown domain"))
        if userURI.username in self.users:
            dc, url = self.users[userURI.username]
            return defer.succeed(url)
        else:
            return defer.fail(LookupError("no such user"))

    def getRegistrationInfo(self, userURI):
        if userURI.host != self.domain:
            return defer.fail(LookupError("unknown domain"))
        if self.users.has_key(userURI.username):
            dc, url = self.users[userURI.username]
            return defer.succeed(Registration(int(dc.getTime() - time.time()), url))
        else:
            return defer.fail(LookupError("no such user"))

    def _expireRegistration(self, username):
        try:
            dc, url = self.users[username]
        except KeyError:
            return defer.fail(LookupError("no such user"))
        else:
            dc.cancel()
            del self.users[username]
        return defer.succeed(Registration(0, url))

    def registerAddress(self, domainURL, logicalURL, physicalURL):
        if domainURL.host != self.domain:
            log.msg("Registration for domain we don't handle.")
            return defer.fail(RegistrationError(404))
        if logicalURL.host != self.domain:
            log.msg("Registration for domain we don't handle.")
            return defer.fail(RegistrationError(404))
        if logicalURL.username in self.users:
            dc, old = self.users[logicalURL.username]
            dc.reset(3600)
        else:
            dc = reactor.callLater(3600, self._expireRegistration, logicalURL.username)
        log.msg("Registered %s at %s" % (logicalURL.toString(), physicalURL.toString()))
        self.users[logicalURL.username] = (dc, physicalURL)
        return defer.succeed(Registration(int(dc.getTime() - time.time()), physicalURL))

    def unregisterAddress(self, domainURL, logicalURL, physicalURL):
        return self._expireRegistration(logicalURL.username)
