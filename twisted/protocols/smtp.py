# -*- test-case-name: twisted.test.test_smtp -*-
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

from __future__ import generators

# Twisted imports
from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import protocol
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.interfaces import ITLSTransport
from twisted.python import log
from twisted.python import components
from twisted.python import util
from twisted.python import reflect
from twisted.python import failure

from twisted import cred
import twisted.cred.checkers
import twisted.cred.credentials

# System imports
import time, string, re, base64, types, socket, os, random
import MimeWriter, tempfile, rfc822
import warnings
import binascii
import sys

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

DNSNAME = socket.getfqdn() # Cache the hostname

# Used for fast success code lookup
SUCCESS = dict(map(None, range(200, 300), []))

class IMessageDelivery(components.Interface):
    def receivedHeader(self, helo, origin, recipients):
        """
        Generate the Received header for a message

        @type helo: C{(str, str)}
        @param helo: The argument to the HELO command and the client's IP
        address.

        @type origin: C{Address}
        @param origin: The address the message is from

        @type recipients: C{list} of C{str}
        @param recipients: A list of the addresses for which this message
        is bound.

        @rtype: C{str}
        @return: The full "Received" header string.
        """

    def validateTo(self, user):
        """
        Validate the address for which the message is destined.

        @type user: C{User}
        @param user: The address to validate.

        @rtype: no-argument callable
        @return: A C{Deferred} which becomes, or a callable which
        takes no arguments and returns an object implementing C{IMessage}.
        This will be called and the returned object used to deliver the
        message when it arrives.

        @raise SMTPBadRcpt: Raised if messages to the address are
        not to be accepted.
        """

    def validateFrom(self, helo, origin):
        """
        Validate the address from which the message originates.

        @type helo: C{(str, str)}
        @param helo: The argument to the HELO command and the client's IP
        address.

        @type origin: C{Address}
        @param origin: The address the message is from

        @rtype: C{Deferred} or C{Address}
        @return: C{origin} or a C{Deferred} whose callback will be
        passed C{origin}.

        @raise SMTPBadSender: Raised of messages from this address are
        not to be accepted.
        """

class IMessageDeliveryFactory(components.Interface):
    """An alternate interface to implement for handling message delivery.

    It is useful to implement this interface instead of L{IMessageDelivery}
    directly because it allows the implementor to distinguish between
    different messages delivery over the same connection.  This can be
    used to optimize delivery of a single message to multiple recipients,
    something which cannot be done by L{IMessageDelivery} implementors
    due to their lack of information.
    """
    def getMessageDelivery(self):
        """Return an L{IMessageDelivery} object.

        This will be called once per message.
        """

class SMTPError(Exception):
    pass

class SMTPClientError(SMTPError):
    def __init__(self, code, resp, log=None, addresses=None):
        self.code = code
        self.resp = resp
        self.log = log
        self.addresses = addresses

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

def rfc822date(timeinfo=None,local=1):
    """
    Format an RFC-2822 compliant date string.

    @param timeinfo: (optional) A sequence as returned by C{time.localtime()}
        or C{time.gmtime()}. Default is now.
    @param local: (optional) Indicates if the supplied time is local or
        universal time, or if no time is given, whether now should be local or
        universal time. Default is local, as suggested (SHOULD) by rfc-2822.

    @returns: A string representing the time and date in RFC-2822 format.
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

def idGenerator():
    i = 0
    while True:
        yield i
        i += 1

def messageid(uniq=None, N=idGenerator().next):
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

    return '<%s.%s.%s%s.%s@%s>' % (datetime, pid, rand, uniq, N(), DNSNAME)

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

COMMAND, DATA, AUTH = 'COMMAND', 'DATA', 'AUTH'

class AddressError(SMTPError):
    "Parse error in address"

# Character classes for parsing addresses
atom = r"[-A-Za-z0-9!\#$%&'*+/=?^_`{|}~]"

class Address:
    """Parse and hold an RFC 2821 address.

    Source routes are stipped and ignored, UUCP-style bang-paths
    and %-style routing are not parsed.

    @type domain: C{str}
    @ivar domain: The domain within which this address resides.

    @type local: C{str}
    @ivar local: The local (\"user\") portion of this address.
    """

    tstring = re.compile(r'''( # A string of
                          (?:"[^"]*" # quoted string
                          |\\. # backslash-escaped characted
                          |''' + atom + r''' # atom character
                          )+|.) # or any single character''',re.X)
    atomre = re.compile(atom) # match any one atom character

    def __init__(self, addr, defaultDomain=None):
        if isinstance(addr, User):
            addr = addr.dest
        if isinstance(addr, Address):
            self.__dict__ = addr.__dict__.copy()
            return
        elif not isinstance(addr, types.StringTypes):
            addr = str(addr)
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
            elif len(atl[0]) == 1 and not self.atomre.match(atl[0]) and atl[0] !=  '.':
                raise AddressError, "Parse error at %r of %r" % (atl[0], (addr, atl))
            else:
                if not domain:
                    local.append(atl[0])
                else:
                    domain.append(atl[0])
                atl = atl[1:]

        self.local = ''.join(local)
        self.domain = ''.join(domain)
        if self.domain == '':
            if defaultDomain is None:
                defaultDomain = DNSNAME
            self.domain = defaultDomain

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
        return '@'.join((self.local, self.domain))

    def __repr__(self):
        return "%s.%s(%s)" % (self.__module__, self.__class__.__name__,
                              repr(str(self)))

class User:
    """Hold information about and SMTP message recipient,
    including information on where the message came from
    """

    def __init__(self, destination, helo, protocol, orig):
        host = getattr(protocol, 'host', None)
        self.dest = Address(destination, host)
        self.helo = helo
        self.protocol = protocol
        if isinstance(orig, Address):
            self.orig = orig
        else:
            self.orig = Address(orig, host)

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

class SMTP(basic.LineReceiver, policies.TimeoutMixin):
    """SMTP server-side protocol."""

    timeout = 600
    host = DNSNAME
    portal = None

    # A factory for IMessageDelivery objects.  If an
    # avatar implementing IMessageDeliveryFactory can
    # be acquired from the portal, it will be used to
    # create a new IMessageDelivery object for each
    # message which is received.
    deliveryFactory = None

    # An IMessageDelivery object.  A new instance is
    # used for each message received if we can get an
    # IMessageDeliveryFactory from the portal.  Otherwise,
    # a single instance is used throughout the lifetime
    # of the connection.
    delivery = None

    # Cred cleanup function.
    _onLogout = None

    def __init__(self, delivery=None, deliveryFactory=None):
        self.mode = COMMAND
        self._from = None
        self._helo = None
        self._to = []
        self.delivery = delivery
        self.deliveryFactory = deliveryFactory

    def timeoutConnection(self):
        msg = '%s Timeout. Try talking faster next time!' % (self.host,)
        self.sendCode(421, msg)
        self.transport.loseConnection()

    def greeting(self):
        return '%s NO UCE NO UBE NO RELAY PROBES ESMTP' % (self.host,)

    def connectionMade(self):
        # Ensure user-code always gets something sane for _helo
        peer = self.transport.getPeer()
        try:
            host = peer.host
        except AttributeError: # not a UPV4Address
            host = str(peer)
        self._helo = (None, host)
        self.sendCode(220, self.greeting())
        self.setTimeout(self.timeout)

    def sendCode(self, code, message=''):
        "Send an SMTP code with a message."
        lines = message.splitlines()
        lastline = lines[-1:]
        for line in lines[:-1]:
            self.sendLine('%3.3d-%s' % (code, line))
        self.sendLine('%3.3d %s' % (code,
                                    lastline and lastline[0] or ''))

    def lineReceived(self, line):
        self.resetTimeout()
        return getattr(self, 'state_' + self.mode)(line)

    def state_COMMAND(self, line):
        words = line.split(None, 1)
        try:
            command = words[0]
        except IndexError:
            self.sendSyntaxError()
        else:
            method = self.lookupMethod(command)
            if method is None:
                method = self.do_UNKNOWN
            method(line[len(command):].strip())

    def sendSyntaxError(self):
        self.sendCode(500, 'Error: bad syntax')

    def lookupMethod(self, command):
        return getattr(self, 'do_' + command.upper(), None)

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
        peer = self.transport.getPeer()
        try:
            host = peer.host
        except AttributeError:
            host = str(peer)
        self._helo = (rest, host)
        self._from = None
        self._to = []
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
        if self._from:
            self.sendCode(503,"Only one sender per message, please")
            return
        # Clear old recipient list
        self._to = []
        m = self.mail_re.match(rest)
        if not m:
            self.sendCode(501, "Syntax error")
            return

        try:
            addr = Address(m.group('path'), self.host)
        except AddressError, e:
            self.sendCode(553, str(e))
            return

        defer.maybeDeferred(self.validateFrom, self._helo, addr
            ).addCallbacks(self._cbFromValidate, self._ebFromValidate
            )

    def _cbFromValidate(self, from_, code=250, msg='Sender address accepted'):
        self._from = from_
        self.sendCode(code, msg)

    def _ebFromValidate(self, failure):
        if failure.check(SMTPBadSender):
            self.sendCode(failure.value.code,
                          'Cannot receive for specified address %s: %s'
                          % (repr(str(failure.value.addr)), failure.value.resp))
        elif failure.check(SMTPServerError):
            self.sendCode(failure.value.code, failure.value.resp)
        else:
            log.err(failure)
            self.sendCode(
                451,
                'Requested action aborted: local error in processing'
            )


    def do_RCPT(self, rest):
        if not self._from:
            self.sendCode(503, "Must have sender before recipient")
            return
        m = self.rcpt_re.match(rest)
        if not m:
            self.sendCode(501, "Syntax error")
            return

        try:
            user = User(m.group('path'), self._helo, self, self._from)
        except AddressError, e:
            self.sendCode(553, str(e))
            return

        d = defer.maybeDeferred(self.validateTo, user)
        d.addCallbacks(
            self._cbToValidate,
            self._ebToValidate,
            callbackArgs=(user,)
        )

    def _cbToValidate(self, to, user=None, code=250, msg='Recipient address accepted'):
        if user is None:
            user = to
        self._to.append((user, to))
        self.sendCode(code, msg)

    def _ebToValidate(self, failure):
        if failure.check(SMTPBadRcpt, SMTPServerError):
            self.sendCode(failure.value.code, failure.value.resp)
        else:
            log.err(failure)
            self.sendCode(
                451,
                'Requested action aborted: local error in processing'
            )

    def do_DATA(self, rest):
        if self._from is None or (not self._to):
            self.sendCode(503, 'Must have valid receiver and originator')
            return
        assert self.delivery
        self.mode = DATA
        helo, origin = self._helo, self._from
        recipients = self._to

        self._from = None
        self._to = []
        self.datafailed = None

        try:
            self.__messages = [f() for (u, f) in recipients]
        except SMTPServerError, e:
            self.sendCode(e.code, e.resp)
            self.mode = COMMAND
            return
        except:
            log.err()
            self.sendCode(550, "Internal server error")
            self.mode = COMMAND
            return

        rcvdhdr = self.delivery.receivedHeader(
            helo, origin, [u for (u, f) in recipients])

        self.__inheader = self.__inbody = 0
        if rcvdhdr:
            try:
                for message in self.__messages:
                    message.lineReceived(rcvdhdr)
            except SMTPServerError, e:
                self.sendCode(e.code, e.resp)
                self.mode = COMMAND
                return
        self.sendCode(354, 'Continue')
        fmt = 'Receiving message for delivery: from=%s to=%s'
        log.msg(fmt % (origin, [str(u) for (u, f) in recipients]))

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
        if self._onLogout:
            self._onLogout()
            self._onLogout = None
        self.setTimeout(None)

    def do_RSET(self, rest):
        self._from = None
        self._to = []
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
                defer.DeferredList([
                    m.eomReceived() for m in self.__messages
                ]).addCallback(self._messageHandled
                ).addErrback(self._messageNotHandled)
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
    state_DATA = dataLineReceived

    def _messageHandled(self, _):
        self.sendCode(250, 'Delivery in progress')
        log.msg('Accepted message for delivery')

    def _messageNotHandled(self, failure):
        if failure.check(SMTPServerError):
            self.sendCode(failure.value.code, failure.value.resp)
            fmt = 'Message not handled: (%d) %s'
            log.msg(fmt % (failure.value.code, failure.value.resp))
        else:
            self.sendCode(550, 'Could not send e-mail')
            log.msg('Message not handled: (550) Could not send e-mail')
        log.err(failure)

    def _cbAuthenticated(self, (iface, avatar, logout)):
        if issubclass(iface, IMessageDeliveryFactory):
            self.deliveryFactory = avatar
            self.delivery = None
        elif issubclass(iface, IMessageDelivery):
            self.deliveryFactory = None
            self.delivery = avatar
        else:
            raise RuntimeError("%s is not a supported interface" % (iface.__name__,))
        self._onLogout = logout
        self.authenticated = 1
        self.challenger = None

    def _ebAuthenticated(self, reason):
        self.challenge = None
        if reason.check(cred.error.UnauthorizedLogin):
            self.sendCode(535, 'Authentication failed')
        elif reason.check(SMTPAddressError):
            self.sendCode(reason.value.code, reason.value.resp)
        else:
            self.sendCode(451, 'Requested action aborted: local error in processing')
            log.err(reason)

    # overridable methods:
    def validateFrom(self, helo, origin):
        """
        Validate the address from which the message originates.

        @type helo: C{(str, str)}
        @param helo: The argument to the HELO command and the client's IP
        address.

        @type origin: C{Address}
        @param origin: The address the message is from

        @rtype: C{Deferred} or C{Address}
        @return: C{origin} or a C{Deferred} whose callback will be
        passed C{origin}.

        @raise SMTPBadSender: Raised of messages from this address are
        not to be accepted.
        """
        if self.deliveryFactory is not None:
            self.delivery = self.deliveryFactory.getMessageDelivery()

        if self.delivery is not None:
            return defer.maybeDeferred(self.delivery.validateFrom,
                                       helo, origin)

        # No login has been performed, no default delivery object has been
        # provided: try to perform an anonymous login and then invoke this
        # method again.
        if self.portal:
            return self.portal.login(cred.credentials.Anonymous(), None,
                    IMessageDeliveryFactory, IMessageDelivery
                ).addCallback(self._cbAuthenticated
                ).addCallback(lambda _: self.validateFrom(helo, origin)
                ).addErrback(self._ebAuthenticated
                )
        raise SMTPBadSender(origin)

    def validateTo(self, user):
        """
        Validate the address for which the message is destined.

        @type user: C{User}
        @param user: The address to validate.

        @rtype: no-argument callable
        @return: A C{Deferred} which becomes, or a callable which
        takes no arguments and returns an object implementing C{IMessage}.
        This will be called and the returned object used to deliver the
        message when it arrives.

        @raise SMTPBadRcpt: Raised if messages to the address are
        not to be accepted.
        """
        if self.delivery:
            return self.delivery.validateTo(user)
        raise SMTPBadRcpt(user)

    def startMessage(self, recipients):
        if self.delivery:
            return self.delivery.startMessage(recipients)
        return []


class SMTPFactory(protocol.ServerFactory):
    """Factory for SMTP."""

    # override in instances or subclasses
    domain = DNSNAME
    timeout = 600
    protocol = SMTP

    portal = None

    def __init__(self, portal = None):
        self.portal = portal

    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)
        p.portal = self.portal
        p.host = self.domain
        return p

class SMTPClient(basic.LineReceiver):
    """SMTP client for sending emails."""

    def __init__(self, identity, logsize=10):
        self.identity = identity or ''
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
            return SMTPProtocolError(code, resp, str(self.log))
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
            if code in SUCCESS:
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
        s = basic.FileSender()
        s.beginFileTransfer(
            self.getMailData(), self.transport, self.transformChunk
        ).addCallback(self.finishedFileTransfer)
        self._expected = SUCCESS
        self._okresponse = self.smtpState_msgSent

    def smtpState_msgSent(self, code, resp):
        if self._from is not None:
            # If there was a pending message
            self.sentMail(code, resp, len(self.successAddresses),
                          self.toAddressesResult, self.log)

        self.toAddressesResult = []
        self._from = None
        self.sendLine('RSET')
        self._expected = SUCCESS
        self._okresponse = self.smtpState_from

    ##
    ## Helpers for FileSender
    ##
    def transformChunk(self, chunk):
        return chunk.replace('\n', '\r\n').replace('\r\n.', '\r\n..')

    def finishedFileTransfer(self, lastsent):
        if lastsent != '\n':
            line = '\r\n.'
        else:
            line = '.'
        self.sendLine(line)
    ##

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

        @param numOK: the number of addresses accepted by the remote host.

        @param addresses: is a list of tuples (address, code, resp) listing
            the response to each RCPT command.

        @param log: is the SMTP session log
        """
        raise NotImplementedError

class ESMTPClient(SMTPClient):
    # Fall back to HELO if the server does not support EHLO
    heloFallback = 1

    # Refuse to proceed if authentication cannot be performed
    requireAuthentication = 0

    # Refuse to proceed if TLS is not available
    requireTransportSecurity = 0

    # ClientContextFactory to use for STARTTLS
    context = None

    def __init__(self, secret, contextFactory=None, *args, **kw):
        SMTPClient.__init__(self, *args, **kw)
        self.authenticators = {}
        self.secret = secret
        self.context = contextFactory

    def registerAuthenticator(self, auth):
        self.authenticators[auth.getName().upper()] = auth

    def connectionMade(self):
        self._expected = [220]
        self._okresponse = self.esmtpState_ehlo
        self._failresponse = self.smtpConnectionFailed

    def esmtpState_ehlo(self, code, resp):
        self.sendLine('EHLO ' + self.identity)
        self._expected = SUCCESS
        self._okresponse = self.esmtpState_auth
        if self.heloFallback:
            self._failresponse = self.smtpState_helo

    def esmtpState_auth(self, code, resp):
        scheme = None
        items = {}
        for line in resp.splitlines():
            e = line.split(None, 1)
            if len(e) > 1:
                items[e[0]] = e[1]
            else:
                items[e[0]] = None

        if self.context and 'STARTTLS' in items:
            self._expected = [220]
            self._okresponse = self.esmtpState_starttls
            self._carryon = items
            self.sendLine('STARTTLS')
        elif self.requireTransportSecurity:
            log.msg("TLS required but not available: closing connection")
            self.sendLine('QUIT')
            self._expected = xrange(0, 1000)
            self._okresponse = self.smtpState_disconnect
        else:
            self.authenticate(code, resp, items)

    def esmtpState_starttls(self, code, resp):
        self.transport.startTLS(self.context)
        items = self._carryon
        self._carryon = None
        self.authenticate(code, resp, items)

    def authenticate(self, code, resp, items):
        if self.secret and items.get('AUTH'):
            schemes = items['AUTH'].split()
            for s in schemes:
                if s.upper() in self.authenticators:
                    self.sendLine('AUTH ' + s)
                    self._expected = [334]
                    self._okresponse = self.esmtpState_challenge
                    self._authinfo = self.authenticators[s]
                    return
        if self.requireAuthentication:
            log.msg("Authentication required but none available: closing connection")
            self.sendLine('QUIT')
            self._expected = xrange(0, 1000)
            self._okresponse = self.smtpState_disconnect
        else:
            self.smtpState_from(code, resp)

    def esmtpState_challenge(self, code, resp):
        auth = self._authinfo
        del self._authinfo
        self._authResponse(auth, resp)

    def _authResponse(self, auth, challenge):
        try:
            challenge = base64.decodestring(challenge)
        except binascii.Error, e:
            # Illegal challenge, give up, then quit
            self.sendLine('*')
            self._okresponse = self.smtpState_disconnect
            self._failresponse = self.smtpState_disconnect
        else:
            resp = auth.challengeResponse(self.secret, challenge)
            self.sendLine(base64.encodestring(resp))
            self._okresponse = self.smtpState_from
            self._failresponse = self.smtpState_disconnect

class ESMTP(SMTP):

    ctx = None
    canStartTLS = False
    startedTLS = False

    authenticated = False

    def __init__(self, chal = None, contextFactory = None):
        SMTP.__init__(self)
        if chal is None:
            chal = {}
        self.challengers = chal
        self.authenticated = False
        self.ctx = contextFactory

    def connectionMade(self):
        SMTP.connectionMade(self)
        self.canStartTLS = components.implements(self.transport, ITLSTransport)
        self.canStartTLS = self.canStartTLS and (self.ctx is not None)

    def extensions(self):
        ext = {'AUTH': self.challengers.keys()}
        if self.canStartTLS and not self.startedTLS:
            ext['STARTTLS'] = None
        return ext

    def lookupMethod(self, command):
        m = SMTP.lookupMethod(self, command)
        if m is None:
            m = getattr(self, 'ext_' + command.upper(), None)
        return m

    def listExtensions(self):
        r = []
        for (c, v) in self.extensions().iteritems():
            if v is not None:
                if v:
                    # Intentionally omit extensions with empty argument lists
                    r.append('%s %s' % (c, ' '.join(v)))
            else:
                r.append(c)
        return '\n'.join(r)

    def do_EHLO(self, rest):
        peer = self.transport.getPeer().host
        self._helo = (rest, peer)
        self._from = None
        self._to = []
        self.sendCode(
            250,
            '%s Hello %s, nice to meet you\n%s' % (
                self.host, peer,
                self.listExtensions(),
            )
        )

    def ext_STARTTLS(self, rest):
        if self.startedTLS:
            self.sendCode(503, 'TLS already negotiated')
        elif self.ctx and self.canStartTLS:
            self.sendCode(220, 'Begin TLS negotiation now')
            self.transport.startTLS(self.ctx)
            self.startedTLS = True
        else:
            self.sendCode(454, 'TLS not available')

    def ext_AUTH(self, rest):
        if self.authenticated:
            self.sendCode(503, 'Already authenticated')
            return
        parts = rest.split(None, 1)
        chal = self.challengers.get(parts[0].upper(), lambda: None)()
        if not chal:
            self.sendCode(504, 'Unrecognized authentication type')
            return
        self.authenticate(chal)

    def authenticate(self, challenger):
        if self.portal:
            challenge = challenger.getChallenge()
            coded = base64.encodestring(challenge)[:-1]
            self.sendCode(334, coded)
            self.mode = AUTH
            self.challenger = challenger
        else:
            self.sendCode(454, 'Temporary authentication failure')

    def state_AUTH(self, rest):
        self.mode = COMMAND

        if rest == '*':
            self.sendCode(501, 'Authentication aborted')
            self.challenger.abort()
            self.challenger = None
            return

        try:
            uncoded = base64.decodestring(rest)
        except binascii.Error, e:
            self._ebAuthenticated(failure.Failure(e))
        else:
            self.challenger.setResponse(uncoded)
            if self.challenger.moreChallenges():
                self.authenticate(self.challenger)
            else:
                self.portal.login(self.challenger, None,
                        IMessageDeliveryFactory, IMessageDelivery
                    ).addCallback(self._cbAuthenticated
                    ).addCallback(lambda _: self.sendCode(235, 'Authentication successful.')
                    ).addErrback(self._ebAuthenticated
                    )

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
        if code not in SUCCESS:
            # Failure
            errlog = []
            for addr, acode, aresp in addresses:
                if code not in SUCCESS:
                    errlog.append("%s: %03d %s" % (addr, acode, aresp))
            if numOk:
                errlog.append(str(log))
            exc = SMTPDeliveryError(code, resp, '\n'.join(errlog), addresses)
            self.factory.result.errback(exc)
        else:
            self.factory.result.callback((numOk, addresses))


class SMTPSenderFactory(protocol.ClientFactory):
    """
    Utility factory for sending emails easily.
    """

    domain = DNSNAME
    protocol = SMTPSender

    def __init__(self, fromEmail, toEmail, file, deferred, retries=5):
        if isinstance(toEmail, types.StringTypes):
            toEmail = [toEmail]
        self.fromEmail = Address(fromEmail)
        self.toEmail = toEmail
        self.file = file
        self.result = deferred
        self.result.addBoth(self._removeDeferred)
        self.sendFinished = 0
        self.retries = -retries

    def _removeDeferred(self, argh):
        del self.result
        return argh

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
        p = self.protocol(self.domain, len(self.toEmail)*2+2)
        p.factory = self
        return p

def sendmail(smtphost, from_addr, to_addrs, msg):
    """Send an email

    This interface is intended to be a direct replacement for
    smtplib.SMTP.sendmail() (with the obvious change that
    you specify the smtphost as well). Also, ESMTP options
    are not accepted, as we don't do ESMTP yet. I reserve the
    right to implement the ESMTP options differently.

    @param smtphost: The host the message should be sent to
    @param from_addr: The (envelope) address sending this mail.
    @param to_addrs: A list of addresses to send this mail to.  A string will
        be treated as a list of one address
    @param msg: The message, including headers, either as a file or a string.
        File-like objects need to support read() and close(). Line endings
        must be local (i.e. '\\n'). If you pass something that doesn't look
        like a file, we try to convert it to a string (so you should be able
        to pass an email.Message directly, but doing the conversion with
        email.Generator manually will give you more control over the
        process).

    @rtype: L{Deferred}
    @returns: A L{Deferred}, its callback will be called if a message is sent
        to ANY address, the errback if no message is sent.

        The callback will be called with a tuple (numOk, addresses) where numOk
        is the number of successful recipient addresses and addresses is a list
        of tuples (address, code, resp) giving the response to the RCPT command
        for each address.
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

##
## Yerg.  Codecs!
##
import codecs
def xtext_encode(s):
    r = []
    for ch in s:
        o = ord(ch)
        if ch == '+' or ch == '=' or o < 33 or o > 126:
            r.append('+%02X' % o)
        else:
            r.append(ch)
    return (''.join(r), len(s))

try:
    from twisted.protocols._c_urlarg import unquote as _helper_unquote
except ImportError:
    def xtext_decode(s):
        r = []
        i = 0
        while i < len(s):
            if s[i] == '+':
                try:
                    r.append(chr(int(s[i + 1:i + 3], 16)))
                except ValueError:
                    r.append(s[i:i + 3])
                i += 3
            else:
                r.append(s[i])
                i += 1
        return (''.join(r), len(s))
else:
    def xtext_decode(s):
        return (_helper_unquote(s, '+'), len(s))

class xtextStreamReader(codecs.StreamReader):
    def decode(self, s, errors='strict'):
        return xtext_decode(s)

class xtextStreamWriter(codecs.StreamWriter):
    def decode(self, s, errors='strict'):
        return xtext_encode(s)

def xtext_codec(name):
    if name == 'xtext':
        return (xtext_encode, xtext_decode, xtextStreamReader, xtextStreamWriter)
codecs.register(xtext_codec)
