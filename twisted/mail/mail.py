
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

"""Mail support for twisted python.
"""

# Twisted imports
from twisted.protocols import smtp, http
from twisted.cred import service
from twisted.python import components
from twisted.internet import defer

# Sibling imports
import protocols

# System imports
import MimeWriter
import tempfile
import types
import time
import os


class DomainWithDefaultDict:
    '''Simulate a dictionary with a default value for non-existing keys.
    '''
    def __init__(self, domains, default):
        self.domains = domains
        self.default = default

    def setDefaultDomain(self, domain):
        self.default = domain
    
    def has_key(self, name):
        return 1

    def __getitem__(self, name):
        return self.domains.get(name, self.default)

    def __setitem__(self, name, value):
        self.domains[name] = value


class BounceDomain:
    """A domain in which no user exists. 

    This can be used to block off certain domains.
    """
    def exists(self, user, success, failure):
        """No user exists in a BounceDomain -- always return 0
        """
        failure(user)


class FileMessage:
    """A file we can write an email too."""
    
    __implements__ = smtp.IMessage

    def __init__(self, fp, name, finalName):
        self.fp = fp
        self.name = name
        self.finalName = finalName

    def lineReceived(self, line):
        self.fp.write(line+'\n')

    def eomReceived(self):
        self.fp.close()
        os.rename(self.name, self.finalName)
        deferred = defer.Deferred()
        deferred.callback(self.finalName)
        return deferred

    def connectionLost(self):
        self.fp.close()
        os.remove(self.name)


class IDomain(components.Interface):
    """An email domain."""


class MailService(service.Service):
    """An email service."""

    def __init__(self, name):
        service.Service.__init__(self, name)
        self.domains = DomainWithDefaultDict({}, BounceDomain())

    def getPOP3Factory(self):
        return protocols.POP3Factory(self)

    def getSMTPFactory(self):
        return protocols.SMTPFactory(self)

    def setQueue(self, queue):
        """Set the queue for outgoing emails."""
        self.queue = queue


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
    factory = protocols.SMTPClientFactory(fromEmail, toEmail, f, d)
    from twisted.internet import reactor
    reactor.connectTCP(smtphost, 25, factory)

    return d
