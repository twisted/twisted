
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
import traceback
import types
import operator
import urllib
import cgi
import copy
import time
import calendar

#some useful constants
NOT_DONE_YET = 1

# Twisted Imports
from twisted.spread import pb
from twisted.internet import passport, main
from twisted.protocols import http, protocol
from twisted.python import log, reflect, roots
from twisted import copyright
from twisted.manhole import coil

# Sibling Imports
import error
import resource

weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
monthname = [None,
             'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Support for other methods may be implemented on a per-resource basis.
supportedMethods = ('GET', 'HEAD', 'POST')

class UnsupportedMethod(Exception):
    """Raised by a resource when faced with a strange request method.

    RFC 2616 (HTTP 1.1) gives us two choices when faced with this
    situtation: If the type of request is know to us, but not allowed
    for the requested resource, respond with NOT_ALLOWED.  Otherwise,
    if the request is something we don't know how to deal with in any
    case, respond with NOT_IMPLEMENTED.

    When this exception is raised by a Resource's render method, the
    server will make the appropriate response.

    This exception's first argument MUST be a sequence of the methods
    the resource *does* support.
    """

    allowedMethods = ()

    def __init__(self, allowedMethods, *args):
        apply(Exception.__init__, [self, allowedMethods] + args)

        if not operator.isSequenceType(allowedMethods):
            why = "but my first argument is not a sequence."
            s = ("First argument must be a sequence of"
                 " supported methods, %s" % (why,))
            raise TypeError, s


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

def timegm(year, month, day, hour, minute, second):
    """Convert time tuple in GMT to seconds since epoch, GMT"""
    EPOCH = 1970
    assert year >= EPOCH
    assert 1 <= month <= 12
    days = 365*(year-EPOCH) + calendar.leapdays(EPOCH, year)
    for i in range(1, month):
        days = days + calendar.mdays[i]
    if month > 2 and calendar.isleap(year):
        days = days + 1
    days = days + day - 1
    hours = days*24 + hour
    minutes = hours*60 + minute
    seconds = minutes*60 + second
    return seconds

def string_date_time(dateString):
    """Convert an HTTP date string to seconds since epoch."""
    parts = string.split(dateString, ' ')
    day = int(parts[1])
    month = int(monthname.index(parts[2]))
    year = int(parts[3])
    hour, min, sec = map(int, string.split(parts[4], ':'))
    return int(timegm(year, month, day, hour, min, sec))


class Request(pb.Copyable, http.HTTP):

    code = http.OK
    method = "(no method yet)"
    clientproto = "(no clientproto yet)"
    uri = "(no uri yet)"
    site = None

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

    def requestReceived(self, command, path, version, content):
        from string import split
        self.args = {}
        self.stack = []
        self.headers = {}
        self.cookies = [] # outgoing cookies
        
        self.method, self.uri = command, path
        self.clientproto = version
        self.content = content

        x = split(self.uri,'?')

        if len(x) == 1:
            self.path = urllib.unquote(self.uri)
        else:
            if len(x) != 2:
                log.msg("May ignore parts of this invalid URI:",
                        repr(self.uri))
            self.path, argstring = urllib.unquote(x[0]), x[1]
            # parse the argument string
            for kvp in string.split(argstring, '&'):
                keyval = map(urllib.unquote, string.split(kvp, '='))
                if len(keyval) != 2:
                    continue
                key, value = keyval
                arg = self.args[key] = self.args.get(key, [])
                arg.append(value)

        self.process()

    def __repr__(self):
        return '<%s %s %s>'% (self.method, self.uri, self.clientproto)
    
    def process(self):
        "Process a request."
        # Log the request to a file.
        log.msg( self )

        # cache the client information, we'll need this later to be
        # pickled and sent with the request so CGIs will work remotely
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
                    pass #raise 'bad content-type'

            # Resource Identification
            self.server_port = 80
            # XXX ^^^^^^^^^^ Obviously it's not always 80.  figure it
            # out from the URI.
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
        except UnsupportedMethod, e:
            allowedMethods = e.allowedMethods
            if (self.method == "HEAD") and ("GET" in allowedMethods):
                # We must support HEAD (RFC 2616, 5.1.1).  If the resource
                # doesn't, fake it by giving the resource a 'GET' request
                # and then return only the headers -- not the body.

                log.msg("Using GET to fake a HEAD request for %s" % resrc)
                self.method == "GET"
                body = resrc.render(self)

                if body is NOT_DONE_YET:
                    log.msg("Tried to fake a HEAD request for %s, but "
                            "it got away from me." % resrc)
                    # Oh well, I guess we won't include the content
                    # length then.
                else:
                    # XXX: What's this "minus one" for?
                    self.setHeader('content-length', str(len(body)-1))

                self.write('')
                self.finish()

            if self.method in (supportedMethods):
                # We MUST include an Allow header
                # (RFC 2616, 10.4.6 and 14.7)
                self.setHeader('Allow', allowedMethods)
                s = ('''Your browser approached me (at %(URI)s) with'''
                     ''' the method "%(method)s".  I only allow'''
                     ''' the method%(plural)s %(allowed) here.''' % {
                    'URI': self.uri,
                    'method': self.method,
                    'plural': ((len(allowedMethods) > 1) and 's') or '',
                    'allowed': string.join(allowedMethods, ', ')
                    })
                epage = error.ErrorPage(http.NOT_ALLOWED,
                                        "Method Not Allowed", s)
                body = epage.render(self)
            else:
                epage = error.ErrorPage(http.NOT_IMPLEMENTED, "Huh?",
                                        """I don't know how to treat a"""
                                        """ %s request."""
                                        % (self.method))
                body = epage.render(self)
        except:
            io = StringIO.StringIO()
            traceback.print_exc(file=io)
            body = ("<HTML><BODY><br>web.Server Traceback \n\n"
                    "%s\n\n</body></html>\n"
                    % (html.PRE(io.getvalue()),))
            log.msg( "Traceback Follows:" )
            log.msg(io.getvalue())
            self.setResponseCode(http.INTERNAL_SERVER_ERROR)
            self.setHeader('content-type',"text/html")

        # XXX: What's this "minus one" for?

        if self.method == "HEAD":
            if len(body) > 0:
                # This is a Bad Thing (RFC 2616, 9.4)
                log.msg("Warning: HEAD request %s for resource %s is"
                        " returning a message body.  I think I'll eat it."
                        % (self, resrc))
                self.setHeader('content-length',str(len(body)-1))
            self.write('')
        else:
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
                for cookie in self.cookies:
                    self.sendHeader("Set-Cookie", cookie)
                self.endHeaders()
            
            # if this is a "HEAD" request, we shouldn't return any data
            if self.method == "HEAD":
                self.write = lambda data: None
        
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

    def addCookie(self, k, v, expires=None, domain=None, path=None, max_age=None, comment=None, secure=None):
        """Set an outgoing HTTP cookie.
        
        In general, you should consider using sessions instead of cookies,
        see self.getSession and the Session class for details.
        """
        cookie = '%s=%s' % (k, v)
        if expires != None:
            cookie = cookie +"; Expires=%s" % expires
        if domain != None:
            cookie = cookie +"; Domain=%s" % domain
        if path != None:
            cookie = cookie +"; Path=%s" % path
        if max_age != None:
            cookie = cookie +"; Max-Age=%s" % max_age
        if comment != None:
            cookie = cookie +"; Comment=%s" % comment
        if secure:
            cookie = cookie +"; Secure"
        self.cookies.append(cookie)
    
    def view_addCookie(self, k, v, **kwargs):
        """Remote version of addCookie; same interface.
        """
        apply(self.addCookie, (k, v), kwargs)
    
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
            cookiename = string.join(['TWISTED_SESSION'] + self.sitepath, "_")
            sessionCookie = self.getCookie(cookiename)
            if sessionCookie:
                try:
                    self.session = self.site.getSession(sessionCookie)
                except KeyError:
                    pass
            # if it still hasn't been set, fix it up.
            if not self.session:
                self.session = self.site.makeSession()
                self.addCookie(cookiename, self.session.uid)
        self.session.touch()
        return self.session

    def getHost(self):
        return socket.gethostbyaddr(self.transport.getHost()[1])

    def prePathURL(self):
        return 'http://%s/%s' % (self.getHeader("host"),
                                 string.join(self.prepath, '/'))

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

    This utility class contains no functionality, but is used to
    represent a session.
    """
    def __init__(self, site, uid):
        """Initialize a session with a unique ID for that session.
        """
        self.site = site
        self.uid = uid
        self.touch()

    def touch(self):
        self.lastModified = time.time()

    def expire(self):
        # If I haven't been touched in 15 minutes:
        if time.time() - self.lastModified > 900:
            if self.site.sessions.has_key(self.uid):
                log.msg("expired session %s" % self.uid)
                del self.site.sessions[self.uid]
            else:
                log.msg("no session to expire: %s" % self.uid)
        else:
            log.msg("session given the will to live for 30 more minutes")
            main.addTimeout(self.expire, 1800)

version = "TwistedWeb/%s" % copyright.version

class Site(protocol.Factory, coil.Configurable, roots.Collection):
    counter = 0

    def __init__(self, resource):
        """Initialize.
        """
        self.sessions = {}
        self.resource = resource

    # configuration
    
    configTypes = {'resource': resource.Resource}
    configName = 'HTTP Web Site'

    def config_resource(self, res):
        self.resource = res

    def getConfiguration(self):
        return {"resource": self.resource}

    # emulate collection for listing

    def listStaticEntities(self):
        return [['resource', self.resource]]

    def getStaticEntity(self, name):
        if name == 'resource':
            return self.resource

    def configInit(self, container, name):
        from twisted.web import static
        d = static.Data(
            """
            <html><head><title>Blank Page</title></head>
            <body>
            <h1>This Page Left Intentionally Blank</h1>
            </body>
            </html>""",
            "text/html")
        d.isLeaf = 1
        self.__init__(d)

    def __getstate__(self):
        d = copy.copy(self.__dict__)
        d['sessions'] = {}
        return d

    def _mkuid(self):
        """(internal) Generate an opaque, unique ID for a user's session.
        """
        self.counter = self.counter + 1
        return "%sx%s" % (long(time.time()*1000), self.counter)

    def makeSession(self):
        """Generate a new Session instance, and store it for future reference.
        """
        uid = self._mkuid()
        s = Session(self, uid)
        session = self.sessions[uid] = s
        main.addTimeout(s.expire, 1800)
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
        # Sitepath is used to determine cookie names between distributed
        # servers and disconnected sites.
        request.sitepath = copy.copy(request.prepath)
        return self.resource.getChildForRequest(request)

coil.registerClass(Site)

import html
