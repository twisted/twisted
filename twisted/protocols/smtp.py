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
from twisted.python import log, components

# System imports
import time, string, re, base64, types
import MimeWriter, tempfile
import warnings

class SMTPError(Exception):
    pass

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
	if type(orig) in types.StringTypes:
	    self.orig = Address(orig)
	else:
            self.orig = orig

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
            
        self.validateFrom(self.__helo, addr, self._fromValid,
                          self._fromInvalid)

    def _fromValid(self, from_, code=250, msg='From address accepted'):
        self.__from = from_
        self.sendCode(code, msg)

    def _fromInvalid(self, from_, code=550, msg='No mail for you!'):
        self.sendCode(code,msg)

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
            
        self.validateTo(user, self._toValid, self._toInvalid)

    def _toValid(self, to, code=250, msg='Address recognized'):
        self.__to.append(to)
        self.sendCode(code, msg)

    def _toInvalid(self, to, code=550,
                   msg='Cannot receive for specified address'):
        self.sendCode(code, msg)

    def do_DATA(self, rest):
        if self.__from is None or not self.__to:  
            self.sendCode(503, 'Must have valid receiver and originator')
            return
        self.mode = DATA
        helo, origin, recipients = self.__helo, self.__from, self.__to
        self.__from = None
        self.__to = []
        self.__messages = self.startMessage(recipients)
        self.__inheader = self.__inbody = 0
        for message in self.__messages:
            message.lineReceived(self.receivedHeader(helo, origin, recipients))
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

    def _messageHandled(self, _):
        self.sendCode(250, 'Delivery in progress')

    def _messageNotHandled(self, _):
        self.sendCode(550, 'Could not send e-mail')

    def rfc822date(self):
        timeinfo = time.localtime()
        if timeinfo[8]:
            # DST
            tz = -time.altzone
        else:
            tz = -time.timezone
            
        return "%s %+2.2d%2.2d" % (
            time.strftime("%a, %d %b %Y %H:%M:%S", timeinfo),
            tz / 3600, (tz / 60) % 60)

    # overridable methods:
    def receivedHeader(self, helo, origin, recipents):
        return "Received: From %s ([%s]) by %s; %s" % (
            helo[0], helo[1], self.host, self.rfc822date())
    
    def validateFrom(self, helo, origin, success, failure):
        if not helo:
            failure(origin,503,"Who are you? Say HELO first");
            return
        success(origin)

    def validateTo(self, user, success, failure):
        success(user)

    def startMessage(self, recipients):
        return []


class SMTPFactory(protocol.ServerFactory):
    """Factory for SMTP."""

    # override in instances or subclasses
    domain = "localhost"
    timeout = 600

    protocol = SMTP


class SMTPClient(basic.LineReceiver):
    """SMTP client for sending emails."""

    def __init__(self, identity):
        self.identity = identity

    def connectionMade(self):
        self.state = 'helo'

    def lineReceived(self, line):
        if len(line)<4 or (line[3] not in ' -'):
            raise ValueError("invalid line from SMTP server %s" % line)
        if line[3] == '-':
            return
        code = int(line[:3])
        method =  getattr(self, 'smtpCode_%d_%s' % (code, self.state), 
                                self.smtpCode_default)
        method(line[4:])

    def smtpCode_220_helo(self, line):
        self.sendLine('HELO '+self.identity)
        self.state = 'from'

    def smtpCode_250_from(self, line):
        from_ = self.getMailFrom()
        if from_ is not None:
            self.sendLine('MAIL FROM:<%s>' % from_)
            self.state = 'afterFrom'
        else:
            self.sendLine('QUIT')
            self.state = 'quit'

    def smtpCode_250_afterFrom(self, line):
        self.toAddresses = self.getMailTo()
        self.successAddresses = []
        self.state = 'to'
        self.sendToOrData()

    def smtpCode_221_quit(self, line):
        self.transport.loseConnection()

    def smtpCode_default(self, line):
        log.msg("SMTPClient got unexpected message from server -- %s" % line)
        self.transport.loseConnection()

    def sendToOrData(self):
        if not self.toAddresses:
            if self.successAddresses:
                self.sendLine('DATA')
                self.state = 'data'
            else:
                self.sentMail([])
                self.smtpCode_250_from('')
        else:
            self.lastAddress = self.toAddresses.pop()
            self.sendLine('RCPT TO:<%s>' % self.lastAddress)

    def smtpCode_250_to(self, line):
        self.successAddresses.append(self.lastAddress)
        self.sendToOrData()

    def smtpCode_550_to(self, line):
        self.sendToOrData()
        
    def smtpCode_354_data(self, line):
        self.mailFile = self.getMailData()
        self.lastsent = ''
        self.transport.registerProducer(self, 0)

    def smtpCode_250_afterData(self, line):
        self.sentMail(self.successAddresses)
        self.smtpCode_250_from('')

    # IProducer interface
    def resumeProducing(self):
        """Write another """
        chunk = self.mailFile.read(8192)
        if not chunk:
            self.transport.unregisterProducer()
            if self.lastsent != '\n':
                line = '\r\n.'
            else:
                line = '.'
            self.sendLine(line)
            self.state = 'afterData'
            return

        chunk = string.replace(chunk, "\n", "\r\n")
        chunk = string.replace(chunk, "\r\n.", "\r\n..")
        self.transport.write(chunk)
        self.lastsent = chunk[-1]

    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.mailFile.close()


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
        i.e. readline() should return a line ending in '\n'.
        """
        raise NotImplementedError

    def sentMail(self, addresses):
        """Called with list of emails to which we sent the message."""
        pass


class SMTPSender(SMTPClient):
    """Utility class for sending emails easily - use with SMTPSenderFactory."""
    
    done = 0

    def smtpCode_default(self, line):
        """Deal with unexpected SMTP messages."""
        SMTPClient.smtpCode_default(self, line)
        self.sentMail([])
    
    def getMailFrom(self):
        if not self.done:
            self.done = 1
            return self.factory.fromEmail
        else:
            return None

    def getMailTo(self):
        return [self.factory.toEmail]

    def getMailData(self):
        return self.factory.file

    def sentMail(self, addresses):
        self.factory.sendFinished = 1
        self.factory.result.callback(addresses == [self.factory.toEmail])


class SMTPSenderFactory(protocol.ClientFactory):
    """
    Utility factory for sending emails easily.
    """

    protocol = SMTPSender
    
    def __init__(self, fromEmail, toEmail, file, deferred):
        self.fromEmail = fromEmail
        self.toEmail = toEmail
        self.file = file
        self.result = deferred
        self.sendFinished = 0
    
    def clientConnectionFailed(self, connector, error):
        self.result.errback(error)

    def clientConnectionLost(self, connector, error):
        # if email wasn't sent, try again
        if not self.sendFinished:
            connector.connect() # reconnect to SMTP server

    def buildProtocol(self, addr):
        p = self.protocol(self.fromEmail.split('@')[-1])
        p.factory = self
        return p


def sendEmail(smtphost, fromEmail, toEmail, content, headers = None, attachments = None):
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

    @rtype: Deferred
    @return: The returned Deferred has its callback or errback invoked when
      the mail is successfully sent or when an error occurs, respectively.
    """
    f = tempfile.TemporaryFile()
    writer = MimeWriter.MimeWriter(f)

    writer.addheader("Mime-Version", "1.0")
    if headers:
        # Setup the mail headers
        for (header, value) in headers.items():
            writer.addheader(header, value)

    writer.startmultipartbody("mixed")

    # message body
    part = writer.nextpart()
    body = part.startbody("text/plain")
    body.write(content)

    if attachments is not None:
        # add attachments
        for (file, mime, attachment) in attachments:
            part = writer.nextpart()
            part.addheader("Content-Transfer-Encoding", "base64")
            body = part.startbody("%s; name=%s" % (mime, file))
            body.write(base64.encodestring(attachment))

    # finish
    writer.lastpart()

    # send message
    f.seek(0, 0)
    d = defer.Deferred()
    factory = SMTPSenderFactory(fromEmail, toEmail, f, d)
    reactor.connectTCP(smtphost, 25, factory)

    return d
