# -*- test-case-name: twisted.test.test_smtp, twisted.test.test_unix -*-
#
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

"""Simple Mail Transfer Protocol implementation.
"""

# Twisted imports
from twisted.protocols import basic
from twisted.internet import protocol, defer, reactor
from twisted.python import log, components, util

# System imports
import time, string, re, base64, types, socket, os, random
import MimeWriter, tempfile, rfc822
import warnings
from cStringIO import StringIO

SUCCESS = dict(map(None, range(200, 300), []))

class SMTPError(Exception):
    pass

class SMTPClientError(SMTPError):
    def __init__(self, code, resp, log=None):
        self.code = code
        self.resp = resp
        self.log = log

    def __str__(self):
        if self.code > 0:
            res = ["%.3d %s" % (self.code, self.resp)]
        else:
            res = [self.resp]
        if self.log:
            res.append('')
            res.append(self.log)
        return '\n'.join(res)

class SMTPConnectError(SMTPClientError):
    pass

class SMTPProtocolError(SMTPClientError):
    pass

class SMTPDeliveryError(SMTPClientError):
    pass

class SMTPServerError(SMTPError):
    def __init__(self, code, resp):
        self.code = code
        self.resp = resp

    def __str__(self):
        return "%.3d %s" % (self.code, self.resp)

class SMTPAddressError(SMTPServerError):
    def __init__(self, addr, code, resp):
        SMTPServerError.__init__(self, code, resp)
        self.addr = Address(addr)

    def __str__(self):
        return "%.3d <%s>... %s" % (self.code, self.addr, self.resp)
    
class SMTPBadRcpt(SMTPAddressError):
    def __init__(self, addr, code=550,
                 resp='Cannot receive for specified address'):
        SMTPAddressError.__init__(self, addr, code, resp)

class SMTPBadSender(SMTPAddressError):
    def __init__(self, addr, code=550, resp='Sender not acceptable'):
        SMTPAddressError.__init__(self, addr, code, resp)

DNSNAME = socket.getfqdn() # Cache the hostname

def rfc822date(timeinfo=None,local=1):
    """
    Format an RFC-2822 compliant date string.

    Arguments: timeinfo    (optional) A sequence as returned by
                           time.localtime() or time.gmtime(). Default
                           is now.
               local       (optional) Indicates if the supplied time
                           is local or universal time, or if no time
                           is given, whether now should be local or
                           universal time. Default is local, as
                           suggested (SHOULD) by rfc-2822.

    Returns: A string representing the time and date in RFC-2822 format.
    """
    if not timeinfo:
        if local:
            timeinfo = time.localtime()
        else:
            timeinfo = time.gmtime()
    if local:
        if timeinfo[8]:
            # DST
            tz = -time.altzone
        else:
            tz = -time.timezone
            
        (tzhr, tzmin) = divmod(abs(tz), 3600)
        if tz:
            tzhr *= int(abs(tz)/tz)
        (tzmin, tzsec) = divmod(tzmin, 60)
    else:
        (tzhr, tzmin) = (0,0)

    return "%s, %02d %s %04d %02d:%02d:%02d %+03d%02d" % (
        ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][timeinfo[6]],
        timeinfo[2],
        ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][timeinfo[1] - 1],
        timeinfo[0], timeinfo[3], timeinfo[4], timeinfo[5],
        tzhr, tzmin)

def messageid(uniq=None):
    """Return a globally unique random string in RFC 2822 Message-ID format

    <datetime.pid.random@host.dom.ain>

    Optional uniq string will be added to strenghten uniqueness if given.
    """
    datetime = time.strftime('%Y%m%d%H%M%S', time.gmtime())
    pid = os.getpid()
    rand = random.randrange(2**31L-1)
    if uniq is None:
        uniq = ''
    else:
        uniq = '.' + uniq

    return '<%s.%s.%s%s@%s>' % (datetime, pid, rand, uniq, DNSNAME)

def quoteaddr(addr):
    """Turn an email address, possibly with realname part etc, into
    a form suitable for and SMTP envelope.
    """

    if isinstance(addr, Address):
        return '<%s>' % str(addr)
    
    res = rfc822.parseaddr(addr)

    if res == (None, None):
        # It didn't parse, use it as-is
        return '<%s>' % str(addr)
    else:
        return '<%s>' % str(res[1])

COMMAND, DATA = range(2)

class NDeferred:

    def __init__(self, n, deferred):
        self.n = n
        self.deferred = deferred
        self.done = 0

    def callback(self, arg):
        if self.done:
            return
        self.n = self.n - 1
        if self.n == 0:
            self.deferred.callback(arg)
            self.done = 1

    def errback(self, arg):
        if self.done:
            return
        self.deferred.errback(arg)
        self.done = 1

class AddressError(SMTPError):
    "Parse error in address"

# Character classes for parsing addresses
atom = r"[-A-Za-z0-9!\#$%&'*+/=?^_`{|}~]"

class Address:
    """Parse and hold an RFC 2821 address.

    Source routes are stipped and ignored, UUCP-style bang-paths
    and %-style routing are not parsed.
    """

    tstring = re.compile(r'''( # A string of
                          (?:"[^"]*" # quoted string
                          |\\. # backslash-escaped characted
                          |''' + atom + r''' # atom character
                          )+|.) # or any single character''',re.X)
    atomre = re.compile(atom) # match any one atom character

    def __init__(self, addr):
        if isinstance(addr, User):
            addr = addr.dest
        if isinstance(addr, Address):
            self.__dict__ = addr.__dict__.copy()
            return
        elif not isinstance(addr, types.StringTypes):
            addr = str(addr)
        self.local = ''
        self.domain = ''
        self.addrstr = addr

        # Tokenize
        atl = filter(None,self.tstring.split(addr))

        local = []
        domain = []

        while atl:
            if atl[0] == '<':
                if atl[-1] != '>':
                    raise AddressError, "Unbalanced <>"
                atl = atl[1:-1]
            elif atl[0] == '@':
                atl = atl[1:]
                if not local:
                    # Source route
                    while atl and atl[0] != ':':
                        # remove it
                        atl = atl[1:]
                    if not atl:
                        raise AddressError, "Malformed source route"
                    atl = atl[1:] # remove :
                elif domain:
                    raise AddressError, "Too many @"
                else:
                    # Now in domain
                    domain = ['']
            elif len(atl[0]) == 1 and not self.atomre.match(atl[0]) \
                     and not atl[0] ==  '.':
                raise AddressError, "Parse error at " + atl[0]
            else:
                if not domain:
                    local.append(atl[0])
                else:
                    domain.append(atl[0])
                atl = atl[1:]
               
        self.local = ''.join(local)
        self.domain = ''.join(domain)

    dequotebs = re.compile(r'\\(.)')

    def dequote(self,addr):
        """Remove RFC-2821 quotes from address."""
        res = []

        atl = filter(None,self.tstring.split(str(addr)))

        for t in atl:
            if t[0] == '"' and t[-1] == '"':
                res.append(t[1:-1])
            elif '\\' in t:
                res.append(self.dequotebs.sub(r'\1',t))
            else:
                res.append(t)

        return ''.join(res)

    def __str__(self):
        return '%s%s' % (self.local, self.domain and ("@" + self.domain) or "")

    def __repr__(self):
        return "%s.%s(%s)" % (self.__module__, self.__class__.__name__,
                              repr(str(self)))

class User:
    """Hold information about and SMTP message recipient,
    including information on where the message came from
    """

    def __init__(self, destination, helo, protocol, orig):
        self.dest = Address(destination)
        self.helo = helo
        self.protocol = protocol
        if isinstance(orig, Address):
            self.orig = orig
        else:
            self.orig = Address(orig)

    def __getstate__(self):
        """Helper for pickle.

        protocol isn't picklabe, but we want User to be, so skip it in
        the pickle.
        """
        return { 'dest' : self.dest,
                 'helo' : self.helo,
                 'protocol' : None,
                 'orig' : self.orig }

    def __str__(self):
        return str(self.dest)

    def __getattr__(self,attr):
        attrmap = { 'name' : 'local', 'domain' : 'domain' }
        if attr in attrmap:
            warnings.warn("User.%s is deprecated, use User.dest.%s instead" %
                (attr, attrmap[attr]), category=DeprecationWarning,
                stacklevel=2)
            return getattr(self.dest, attrmap[attr])
        else:
            raise AttributeError, ("'%s' object has no attribute '%s'" %
                (type(self).__name__, attr))

class IMessage(components.Interface):
    """Interface definition for messages that can be sent via SMTP."""
    
    def lineReceived(self, line):
        """handle another line"""

    def eomReceived(self):
        """handle end of message

        return a deferred. The deferred should be called with either:
        callback(string) or errback(error)
        """

    def connectionLost(self):
        """handle message truncated

        semantics should be to discard the message
        """

class SMTP(basic.LineReceiver):
    """SMTP server-side protocol."""
    
    def __init__(self):
        self.mode = COMMAND
        self.__from = None
        self.__helo = None
        self.__to = []

    def timedout(self):
        self.sendCode(421, '%s Timeout. Try talking faster next time!' %
                      self.host)
        self.transport.loseConnection()

    def connectionMade(self):
        self.host = self.factory.domain
        if hasattr(self.factory, 'timeout'):
            self.timeout = self.factory.timeout
        else:
            self.timeout = 600
        self.sendCode(220, '%s Spammers beware, your ass is on fire' %
                      self.host)
        if self.timeout:
            self.timeoutID = reactor.callLater(self.timeout, self.timedout)

    def sendCode(self, code, message=''):
        "Send an SMTP code with a message."
        lines = message.splitlines()
        lastline = lines[-1:]
        for line in lines[:-1]:
            self.transport.write('%3.3d-%s\r\n' % (code, line))
        self.transport.write('%3.3d %s\r\n' % (code,
                                               lastline and lastline[0] or ''))

    def lineReceived(self, line):
        if self.timeout:
            self.timeoutID.cancel()
            self.timeoutID = reactor.callLater(self.timeout, self.timedout)

        if self.mode is DATA:
            return self.dataLineReceived(line)
        if line:
            command = string.split(line, None, 1)[0]
        else:
            command = ''
        method = getattr(self, 'do_'+string.upper(command), None)
        if method is None:
            method = self.do_UNKNOWN
        else:
            line = line[len(command):]
        return method(string.strip(line))

    def lineLengthExceeded(self, line):
        if self.mode is DATA:
            for message in self.__messages:
                message.connectionLost()
            self.mode = COMMAND
            del self.__messages
        self.sendCode(500, 'Line too long')

    def rawDataReceived(self, data):
        """Throw away rest of long line"""
        rest = string.split(data, '\r\n', 1)
        if len(rest) == 2:
            self.setLineMode(rest[1])

    def do_UNKNOWN(self, rest):
        self.sendCode(500, 'Command not implemented')

    def do_HELO(self, rest):
        peer = self.transport.getPeer()[1]
        self.__helo = (rest, peer)
        self.__from = None
        self.__to = []
        self.sendCode(250, '%s Hello %s, nice to meet you' % (self.host, peer))

    def do_QUIT(self, rest):
        self.sendCode(221, 'See you later')
        self.transport.loseConnection()

    # A string of quoted strings, backslash-escaped character or
    # atom characters + '@.,:'
    qstring = r'("[^"]*"|\\.|' + atom + r'|[@.,:])+'

    mail_re = re.compile(r'''\s*FROM:\s*(?P<path><> # Empty <>
                         |<''' + qstring + r'''> # <addr>
                         |''' + qstring + r''' # addr
                         )\s*(\s(?P<opts>.*))? # Optional WS + ESMTP options
                         $''',re.I|re.X)
    rcpt_re = re.compile(r'\s*TO:\s*(?P<path><' + qstring + r'''> # <addr>
                         |''' + qstring + r''' # addr
                         )\s*(\s(?P<opts>.*))? # Optional WS + ESMTP options
                         $''',re.I|re.X)

    def do_MAIL(self, rest):
        if self.__from:
            self.sendCode(503,"Only one sender per message, please")
            return
        # Clear old recipient list
        self.__to = []
        m = self.mail_re.match(rest)
        if not m:
            self.sendCode(501, "Syntax error")
            return

        try:
            addr = Address(m.group('path'))
        except AddressError, e:
            self.sendCode(553, str(e))
            return
            
        try:
            self.validateFrom(self.__helo, addr).addCallbacks(
                self._cbFromValidate, self._ebValidate)
        except TypeError:
            if self.validateFrom.func_code.co_argcount == 5:
                warnings.warn(
                    'File "%s", line %d, in %s\n'
                    '  %s.validateFrom call syntax has changed!\n'
                    '  Please update your code!' %
                    (self.validateFrom.func_code.co_filename,
                     self.validateFrom.func_code.co_firstlineno,
                     self.validateFrom.func_code.co_name,
                     self.__class__.__name__),
                    category=DeprecationWarning,stacklevel=2)
                self.validateFrom(self.__helo, addr, self._cbFromValidate,
                                  self._fromInvalid)
            else:
                raise

    def _fromInvalid(self, from_, code=550, msg='No mail for you!'):
        "For compatibility"
        self.sendCode(code,msg)

    def _cbFromValidate(self, from_, code=250, msg='Sender address accepted'):
        try:
            from_, code, msg = from_
        except TypeError:
            pass
        self.__from = from_
        self.sendCode(code, msg)

    def _ebValidate(self, failure):
        if failure.check(SMTPServerError):
            self.sendCode(failure.value.code, failure.value.resp)
        else:
            self.sendCode(
                451,
                'Requested action aborted: local error in processing')

    def do_RCPT(self, rest):
        if not self.__from:
            self.sendCode(503, "Must have sender before recipient")
            return
        m = self.rcpt_re.match(rest)
        if not m:
            self.sendCode(501, "Syntax error")
            return

        try:
            user = User(m.group('path'), self.__helo, self, self.__from)
        except AddressError, e:
            self.sendCode(553, str(e))
            return

        try:
            self.validateTo(user).addCallbacks(
                self._cbToValidate, self._ebValidate)
        except TypeError:
            if self.validateTo.func_code.co_argcount == 4:
                warnings.warn(
                    'File "%s", line %d, in %s\n'
                    '  %s.validateTo call syntax has changed!\n'
                    '  Please update your code!' %
                    (self.validateTo.func_code.co_filename,
                     self.validateTo.func_code.co_firstlineno,
                     self.validateTo.func_code.co_name,
                     self.__class__.__name__),
                    category=DeprecationWarning,stacklevel=2)
                self.validateTo(user, self._cbToValidate, self._toInvalid)
            else:
                raise

    def _toInvalid(self, to, code=550,
                   msg='Cannot receive for specified address'):
        "For compatibility"
        self.sendCode(code, msg)

    def _cbToValidate(self, to, code=250, msg='Address recognized'):
        if to is not None:
            try:
                to, code, msg = to
            except TypeError:
                pass
            self.__to.append(to)
            self.sendCode(code, msg)
        else:
            self.sendCode(550, 'Cannot receive for specified address')

    def do_DATA(self, rest):
        if self.__from is None or not self.__to:  
            self.sendCode(503, 'Must have valid receiver and originator')
            return
        self.mode = DATA
        helo, origin, recipients = self.__helo, self.__from, self.__to
        self.__from = None
        self.__to = []
        self.datafailed = None
        try:
            self.__messages = self.startMessage(recipients)
        except SMTPServerError, e:
            self.sendCode(e.code, e.resp)
            self.mode = COMMAND
            return
        self.__inheader = self.__inbody = 0
        rcvdhdr = self.receivedHeader(helo, origin, recipients)
        if rcvdhdr:
            try:
                for message in self.__messages:
                    message.lineReceived(rcvdhdr)
            except SMTPServerError, e:
                self.sendCode(e.code, e.resp)
                self.mode = COMMAND
                return
        self.sendCode(354, 'Continue')

    def connectionLost(self, reason):
        # self.sendCode(421, 'Dropping connection.') # This does nothing...
        # Ideally, if we (rather than the other side) lose the connection,
        # we should be able to tell the other side that we are going away.
        # RFC-2821 requires that we try.
        if self.mode is DATA:
            try:
                for message in self.__messages:
                    message.connectionLost()
                del self.__messages
            except AttributeError:
                pass

    def do_RSET(self, rest):
        self.__from = None
        self.__to = []
        self.sendCode(250, 'I remember nothing.')

    def dataLineReceived(self, line):
        if line[:1] == '.':
            if line == '.':
                self.mode = COMMAND
                if self.datafailed:
                    self.sendCode(self.datafailed.code,
                                  self.datafailed.resp)
                    return
                if not self.__messages:
                    self._messageHandled("thrown away")
                    return
                deferred = defer.Deferred()
                deferred.addCallback(self._messageHandled)
                deferred.addErrback(self._messageNotHandled)
                ndeferred = NDeferred(len(self.__messages), deferred)
                for message in self.__messages:
                    deferred = message.eomReceived()
                    deferred.addCallback(ndeferred.callback)
                    deferred.addErrback(ndeferred.errback)
                del self.__messages
                return
            line = line[1:]

        if self.datafailed:
            return

        try:
            # Add a blank line between the generated Received:-header
            # and the message body if the message comes in without any
            # headers
            if not self.__inheader and not self.__inbody:
                if ':' in line:
                    self.__inheader = 1
                elif line:
                    for message in self.__messages:
                        message.lineReceived('')
                    self.__inbody = 1

            if not line:
                self.__inbody = 1

            for message in self.__messages:
                message.lineReceived(line)
        except SMTPServerError, e:
            self.datafailed = e
            for message in self.__messages:
                message.connectionLost()

    def _messageHandled(self, _):
        self.sendCode(250, 'Delivery in progress')

    def _messageNotHandled(self, failure):
        if failure.check(SMTPServerError):
            self.sendCode(failure.value.code, failure.value.resp)
        else:
            self.sendCode(550, 'Could not send e-mail')

    # overridable methods:
    def receivedHeader(self, helo, origin, recipents):
        return "Received: From %s ([%s]) by %s; %s" % (
            helo[0], helo[1], self.host, rfc822date())
    
    def validateFrom(self, helo, origin):
        if not helo:
            return defer.fail(SMTPBadSender(origin, 503,
                                     "Who are you? Say HELO first"))
        return defer.succeed(origin)

    def validateTo(self, user):
        return defer.succeed(user)

    def startMessage(self, recipients):
        return []


class SMTPFactory(protocol.ServerFactory):
    """Factory for SMTP."""

    # override in instances or subclasses
    domain = DNSNAME
    timeout = 600

    protocol = SMTP

class SMTPClient(basic.LineReceiver):
    """SMTP client for sending emails."""

    def __init__(self, identity, logsize=10):
        self.identity = identity
        self.toAddressesResult = []
        self.successAddresses = []
        self._from = None
        self.resp = []
        self.code = -1
        self.lastfailed = 0
        self.log = util.LineLog(logsize)

    def sendLine(self, line):
        "Logging sendLine"
        self.log.append('>>> ' + line)
        basic.LineReceiver.sendLine(self,line)

    def connectionMade(self):
        self._expected = [ 220 ]
        self._okresponse = self.smtpState_helo
        self._failresponse = self.smtpConnectionFailed

    def lineReceived(self, line):
        why = None

        self.log.append('<<< ' + line)
        try:
            self.code = int(line[:3])
        except ValueError:
            self.code = -1
            self.resp = []
            return self._failresponse(
                -1, "Invalid response from SMTP server: %s" % line)


        if line[0] == '0':
            # Verbose informational message, ignore it
            return

        self.resp.append(line[4:])
        
        if line[3:4] == '-':
            # continuation
            return

        if self.code in self._expected:
            why = self._okresponse(self.code,'\n'.join(self.resp))
            self.lastfailed = 0
        elif not self.lastfailed:
            why = self._failresponse(self.code,'\n'.join(self.resp))
            self.lastfailed += 1
        else:
            self.sendLine('QUIT')
            self._expected = xrange(0,1000)
            self._okresponse = self.smtpState_disconnect
            self.lastfailed = 0

        self.code = -1
        self.resp = []
        return why

    def smtpConnectionFailed(self, code, resp):
        return SMTPConnectError(code, resp, str(self.log))

    def smtpTransferFailed(self, code, resp):
        if code < 0:
            # protocol error
            return SMTPProtcolError(code, resp, str(self.log))
        return self.smtpState_msgSent(code, resp)

    def smtpState_helo(self, code, resp):
        self.sendLine('HELO ' + self.identity)
        self._expected = SUCCESS
        self._okresponse = self.smtpState_from

    def smtpState_from(self, code, resp):
        self._from = self.getMailFrom()
        self._failresponse = self.smtpTransferFailed
        if self._from is not None:
            self.sendLine('MAIL FROM:%s' % quoteaddr(self._from))
            self._okresponse = self.smtpState_to
        else:
            self.sendLine('QUIT')
            self._expected = xrange(0,1000)
            self._okresponse = self.smtpState_disconnect

    def smtpState_disconnect(self, code, resp):
        self.transport.loseConnection()

    def smtpState_to(self, code, resp):
        self.toAddresses = self.getMailTo()
        self.toAddressesResult = []
        self.successAddresses = []
        self._okresponse = self.smtpState_toOrData
        self._expected = xrange(0,1000)
        self.lastAddress = None
        return self.smtpState_toOrData(0, '')

    def smtpState_toOrData(self, code, resp):
        if self.lastAddress is not None:
            self.toAddressesResult.append((self.lastAddress, code, resp))
            if 200 <= code <= 299:
                self.successAddresses.append(self.lastAddress)
        if not self.toAddresses:
            if self.successAddresses:
                self.sendLine('DATA')
                self._expected = [ 354 ]
                self._okresponse = self.smtpState_data
            else:
                return self.smtpState_msgSent(-1,'No recipients accepted')
        else:
            self.lastAddress = self.toAddresses.pop()
            self.sendLine('RCPT TO:%s' % quoteaddr(self.lastAddress))

    def smtpState_data(self, code, resp):
        self.mailFile = self.getMailData()
        self.lastsent = ''
        self.transport.registerProducer(self, 0)
        self._expected = SUCCESS
        self._okresponse = self.smtpState_msgSent

    def smtpState_msgSent(self, code, resp):
        if self._from is not None:
            # If there was a pending message
            try:
                self.sentMail(code, resp, len(self.successAddresses),
                              self.toAddressesResult, self.log)
            except TypeError:
                if self.sentMail.func_code.co_argcount == 2:
                    warnings.warn(
                        'File "%s", line %d, in %s\n'
                        '  %s.sentMail call syntax has changed!\n'
                        '  Please update your code!' %
                        (self.sentMail.func_code.co_filename,
                         self.sentMail.func_code.co_firstlineno,
                         self.sentMail.func_code.co_name,
                         self.__class__.__name__),
                        category=DeprecationWarning,stacklevel=2)
                    self.sentMail(self.successAddresses)
                else:
                    raise

        self.toAddressesResult = []
        self._from = None
        self.sendLine('RSET')
        self._exected = xrange(200,300)
        self._okresponse = self.smtpState_from
        
    # IProducer interface
    def resumeProducing(self):
        """Write another """
        if self.mailFile:
            chunk = self.mailFile.read(8192)
        if not self.mailFile or not chunk:
            self.mailFile = None
            self.transport.unregisterProducer()
            if self.lastsent != '\n':
                line = '\r\n.'
            else:
                line = '.'
            self.sendLine(line)
            return

        chunk = string.replace(chunk, "\n", "\r\n")
        chunk = string.replace(chunk, "\r\n.", "\r\n..")
        self.transport.write(chunk)
        self.lastsent = chunk[-1]

    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.mailFile = None

    def connectionLost(self, reason=protocol.connectionDone):
        """We are no longer connected"""
        self.mailFile = None

    # these methods should be overriden in subclasses
    def getMailFrom(self):
        """Return the email address the mail is from."""
        raise NotImplementedError

    def getMailTo(self):
        """Return a list of emails to send to."""
        raise NotImplementedError

    def getMailData(self):
        """Return file-like object containing data of message to be sent.

        The file should be a text file with local line ending convention,
        i.e. readline() should return a line ending in '\\n'.
        """
        raise NotImplementedError

    def sentMail(self, code, resp, numOk, addresses, log):
        """Called when an attempt to send an email is completed.

        If some addresses were accepted, code and resp are the response
        to the DATA command. If no addresses were accepted, code is -1
        and resp is an informative message.

        numOK is the number of addresses accepted by the remote host.
        addresses is a list of tuples (address, code, resp) listing
            the response to each RCPT command.
        log is the SMTP session log
        """
        raise NotImplementedError


class SMTPSender(SMTPClient):
    """Utility class for sending emails easily - use with SMTPSenderFactory."""
    
    done = 0

    def getMailFrom(self):
        if not self.done:
            self.done = 1
            return str(self.factory.fromEmail)
        else:
            return None

    def getMailTo(self):
        return self.factory.toEmail

    def getMailData(self):
        return self.factory.file

    def sentMail(self, code, resp, numOk, addresses, log):
        self.factory.sendFinished = 1
        if code not in xrange(200,300):
            # Failure
            errlog = []
            for addr, acode, aresp in addresses:
                if code not in xrange(200,300):
                    errlog.append("%s: %03d %s" % (addr, acode, aresp))
            if numOk:
                errlog.append(str(log))
            self.factory.result.errback(SMTPDeliveryError(code, resp,
                                                          '\n'.join(errlog)))
        else:
            self.factory.result.callback((numOk, addresses))


class SMTPSenderFactory(protocol.ClientFactory):
    """
    Utility factory for sending emails easily.
    """

    protocol = SMTPSender
    
    def __init__(self, fromEmail, toEmail, file, deferred, retries=5):
        if isinstance(toEmail, types.StringTypes):
            toEmail = [toEmail]
        self.fromEmail = Address(fromEmail)
        self.toEmail = toEmail
        self.file = file
        self.result = deferred
        self.sendFinished = 0
        self.retries = -retries
    
    def clientConnectionFailed(self, connector, error):
        self.result.errback(error)

    def clientConnectionLost(self, connector, error):
        # if email wasn't sent, try again
        if self.retries < self.sendFinished <= 0:
            connector.connect() # reconnect to SMTP server
        elif self.sendFinished <= 0:
            self.result.errback(error)
        self.sendFinished -= 1

    def buildProtocol(self, addr):
        p = self.protocol(DNSNAME, len(self.toEmail)*2+2)
        p.factory = self
        return p

def sendmail(smtphost, from_addr, to_addrs, msg):
    """Send an email

    This interface is intended to be a direct replacement for
    smtplib.SMTP.sendmail() (with the obvious change that
    you specify the smtphost as well). Also, ESMTP options
    are not accepted, as we don't do ESMTP yet. I reserve the
    right to implement the ESMTP options differently.

    Arguments:
      smtphost   : The host the message should be sent to
      from_addr  : The (envelope) address sending this mail.
      to_addrs   : A list of addresses to send this mail to.
                   A string will be treated as a list of one
                   address
      msg        : The message, including headers, either as
                   a file or a string. File-like objects need
                   to support read() and close(). Line endings
                   must be local (i.e. '\\n'). If you pass
                   something that doesn't look like a file,
                   we try to convert it to a string (so you
                   should be able to pass an email.Message
                   directly, but doing the conversion using
                   generator manually and passing the file
                   object is probably more efficient).

    Returns:
      defered    : The callback will be called if a message is
                   sent to ANY address, the errback if no message
                   is sent.

                   The callback will be called with a tuple
                   (numOk, addresses) where numOk is the number
                   of successful recipient addresses and
                   addresses is a list of tuples
                   (address, code, resp) giving the response
                   to the RCPT command for each address.
    """
    if not hasattr(msg,'read'):
        # It's not a file
        msg = StringIO(str(msg))
        
    d = defer.Deferred()
    factory = SMTPSenderFactory(from_addr, to_addrs, msg, d)
    reactor.connectTCP(smtphost, 25, factory)

    return d
    
def sendEmail(smtphost, fromEmail, toEmail, content, headers = None, attachments = None, multipartbody = "mixed"):
    """Send an email, optionally with attachments.

    @type smtphost: str
    @param smtphost: hostname of SMTP server to which to connect
    
    @type fromEmail: str
    @param fromEmail: email address to indicate this email is from
    
    @type toEmail: str
    @param toEmail: email address to which to send this email
    
    @type content: str
    @param content: The body if this email.
    
    @type headers: dict
    @param headers: Dictionary of headers to include in the email

    @type attachments: list of 3-tuples
    @param attachments: Each 3-tuple should consist of the name of the
      attachment, the mime-type of the attachment, and a string that is
      the attachment itself.

    @type multipartbody: str
    @param multipartbody: The type of MIME multi-part body.  Generally
      either "mixed" (as in text and images) or "alternative" (html email
      with a fallback to text/plain).

    @rtype: Deferred
    @return: The returned Deferred has its callback or errback invoked when
      the mail is successfully sent or when an error occurs, respectively.
    """
    warnings.warn("smtp.sendEmail may go away in the future.\n"
                  "  Consider revising your code to use the email module\n"
                  "  and smtp.sendmail.",
                  category=DeprecationWarning, stacklevel=2)

    f = tempfile.TemporaryFile()
    writer = MimeWriter.MimeWriter(f)

    writer.addheader("Mime-Version", "1.0")
    if headers:
        # Setup the mail headers
        for (header, value) in headers.items():
            writer.addheader(header, value)
            
        headkeys = [k.lower() for k in headers.keys()]
    else:
        headkeys = ()

    # Add required headers if not present
    if "message-id" not in headkeys:
        writer.addheader("Message-ID", messageid())
    if "date" not in headkeys:
        writer.addheader("Date", rfc822date())
    if "from" not in headkeys and "sender" not in headkeys:
        writer.addheader("From", fromEmail)
    if "to" not in headkeys and "cc" not in headkeys and "bcc" not in headkeys:
        writer.addheader("To", toEmail)

    writer.startmultipartbody(multipartbody)

    # message body
    part = writer.nextpart()
    body = part.startbody("text/plain")
    body.write(content)

    if attachments is not None:
        # add attachments
        for (file, mime, attachment) in attachments:
            part = writer.nextpart()
            if mime.startswith('text'):
                encoding = "7bit"
            else:
                attachment = base64.encodestring(attachment)
                encoding = "base64"
            part.addheader("Content-Transfer-Encoding", encoding)
            body = part.startbody("%s; name=%s" % (mime, file))
            body.write(attachment)

    # finish
    writer.lastpart()

    # send message
    f.seek(0, 0)
    d = defer.Deferred()
    factory = SMTPSenderFactory(fromEmail, toEmail, f, d)
    reactor.connectTCP(smtphost, 25, factory)

    return d
