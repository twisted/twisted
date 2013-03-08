# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Support for relaying mail for twisted.mail"""

from twisted.mail import smtp
from twisted.python import log
from twisted.internet.address import UNIXAddress

import os

try:
    import cPickle as pickle
except ImportError:
    import pickle

class DomainQueuer:
    """An SMTP domain which add messages to a queue intended for relaying."""

    def __init__(self, service, authenticated=False):
        self.service = service
        self.authed = authenticated

    def exists(self, user):
        """Check whether we will relay

        Call overridable willRelay method
        """
        if self.willRelay(user.dest, user.protocol):
            # The most cursor form of verification of the addresses
            orig = filter(None, str(user.orig).split('@', 1))
            dest = filter(None, str(user.dest).split('@', 1))
            if len(orig) == 2 and len(dest) == 2:
                return lambda: self.startMessage(user)
        raise smtp.SMTPBadRcpt(user)

    def willRelay(self, address, protocol):
        """Check whether we agree to relay

        The default is to relay for all connections over UNIX
        sockets and all connections from localhost.
        """
        peer = protocol.transport.getPeer()
        return self.authed or isinstance(peer, UNIXAddress) or peer.host == '127.0.0.1'

    def startMessage(self, user):
        """Add envelope to queue and returns ISMTPMessage."""
        queue = self.service.queue
        envelopeFile, smtpMessage = queue.createNewMessage()
        try:
            log.msg('Queueing mail %r -> %r' % (str(user.orig), str(user.dest)))
            pickle.dump([str(user.orig), str(user.dest)], envelopeFile)
        finally:
            envelopeFile.close()
        return smtpMessage

class RelayerMixin:

    # XXX - This is -totally- bogus
    # It opens about a -hundred- -billion- files
    # and -leaves- them open!

    def loadMessages(self, messagePaths):
        self.messages = []
        self.names = []
        for message in messagePaths:
            fp = open(message+'-H')
            try:
                messageContents = pickle.load(fp)
            finally:
                fp.close()
            fp = open(message+'-D')
            messageContents.append(fp)
            self.messages.append(messageContents)
            self.names.append(message)
    
    def getMailFrom(self):
        if not self.messages:
            return None
        return self.messages[0][0]

    def getMailTo(self):
        if not self.messages:
            return None
        return [self.messages[0][1]]

    def getMailData(self):
        if not self.messages:
            return None
        return self.messages[0][2]

    def sentMail(self, code, resp, numOk, addresses, log):
        """Since we only use one recipient per envelope, this
        will be called with 0 or 1 addresses. We probably want
        to do something with the error message if we failed.
        """
        if code in smtp.SUCCESS:
            # At least one, i.e. all, recipients successfully delivered
            os.remove(self.names[0]+'-D')
            os.remove(self.names[0]+'-H')
        del self.messages[0]
        del self.names[0]

class SMTPRelayer(RelayerMixin, smtp.SMTPClient):
    def __init__(self, messagePaths, *args, **kw):
        smtp.SMTPClient.__init__(self, *args, **kw)
        self.loadMessages(messagePaths)

class ESMTPRelayer(RelayerMixin, smtp.ESMTPClient):
    def __init__(self, messagePaths, *args, **kw):
        smtp.ESMTPClient.__init__(self, *args, **kw)
        self.loadMessages(messagePaths)
