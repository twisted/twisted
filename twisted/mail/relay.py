# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for relaying mail for L{twisted.mail}.
"""

from twisted.mail import smtp
from twisted.python import log
from twisted.internet.address import UNIXAddress
from twisted.python.filepath import FilePath

try:
    import cPickle as pickle
except ImportError:
    import pickle


class DomainQueuer:
    """
    An SMTP domain which add messages to a queue intended for relaying.
    """

    def __init__(self, service, authenticated=False):
        self.service = service
        self.authed = authenticated


    def exists(self, user):
        """
        Check whether we will relay.

        Calls overridable L{willRelay} method.

        @raise smtp.SMTPBadRcpt: Raised if the given C{user} will not relay.
        """
        if self.willRelay(user.dest, user.protocol):
            # The most cursor form of verification of the addresses
            orig = filter(None, str(user.orig).split('@', 1))
            dest = filter(None, str(user.dest).split('@', 1))
            if len(orig) == 2 and len(dest) == 2:
                return lambda: self.startMessage(user)
        raise smtp.SMTPBadRcpt(user)


    def willRelay(self, address, protocol):
        """
        Check whether we agree to relay.

        The default is to relay for all connections over UNIX
        sockets and all connections from localhost.
        """
        peer = protocol.transport.getPeer()
        return (self.authed or isinstance(peer, UNIXAddress) or
            peer.host == '127.0.0.1')


    def startMessage(self, user):
        """
        Add envelope to queue and returns an SMTP message.
        """
        queue = self.service.queue
        envelopeFile, smtpMessage = queue.createNewMessage()
        try:
            log.msg('Queueing mail %r -> %r' % (str(user.orig),
                str(user.dest)))
            pickle.dump([str(user.orig), str(user.dest)], envelopeFile)
        finally:
            envelopeFile.close()
        return smtpMessage



class RelayerMixin:
    """
    A mixin for relayers.

    @type messages: L{list} of 3-L{tuple} of (E{1}) L{bytes}, (E{2}) L{bytes},
        (E{3}) L{NoneType <types.NoneType>} or L{file}
    @ivar messages: The origination address, the destination address, and, when
        open, the file containing the contents for each message to be relayed
        by this relayer.

    @type names: L{list} of L{bytes}
    @ivar names: The base filenames of messages to be relayed by this relayer.
    """
    def loadMessages(self, messagePaths):
        """
        Load information about messages to be relayed by this relayer.

        @type messagePaths: L{list} of L{bytes}
        @param messagePaths: The base filenames for messages to be relayed by
            this relayer.
        """
        self.messages = []
        self.names = []
        for message in messagePaths:
            fp = self._openFile(message + '-H')
            try:
                messageContents = pickle.load(fp)
            finally:
                fp.close()
            messageContents.append(None)
            self.messages.append(messageContents)
            self.names.append(message)
    
    def getMailFrom(self):
        """
        Return the origination address of the next message to be relayed.

        @rtype: L{bytes}
        @return: The origination address of the next message to be relayed.
        """
        if not self.messages:
            return None
        return self.messages[0][0]

    def getMailTo(self):
        """
        Return the destination address of the next message to be relayed.

        @rtype: L{bytes}
        @return: The destination address of the next message to be relayed.
        """
        if not self.messages:
            return None
        return [self.messages[0][1]]

    def getMailData(self):
        """
        Return the file containing the contents of the next message to be
        relayed.

        @rtype: L{file}
        @return: The file containing the contents of the next message to be
            relayed.
        """
        if not self.messages:
            return None
        fp = self._openFile(self.names[0] + '-D')
        self.messages[0][2] = fp
        return self.messages[0][2]

    def sentMail(self, code, resp, numOk, addresses, log):
        """
        Remove a message from the set of messages to be relayed when the
        attempt to send it is complete.

        If the attempt is successful, the message header and contents files
        will be removed from the relay queue.  Otherwise, they will be left
        there to be resent.

        @type code: L{int}
        @param code: The response code from the server.

        @type resp: L{bytes}
        @param resp: The response string from the server.

        @type numOk: L{int}
        @param numOk: The number of addresses accepted by the server.

        @type addresses: L{list} of 3-L{tuple} of (E{1}) L{bytes},
            (E{2}) L{int}, (E{3}) L{bytes}
        @param addresses: The address, response code and response string from
            the server for each destination address.  Since the message was
            sent to just one address, the list will have just one entry.

        @type log: L{LineLog <twisted.python.util.LineLog>}
        @param log: A log of the SMTP transaction.
        """
        # We probably want to do something with the error message if we failed.
        self.messages[0][2].close()
        if code in smtp.SUCCESS:
            # At least one, i.e. all, recipients successfully delivered
            FilePath(self.names[0] + '-D').remove()
            FilePath(self.names[0] + '-H').remove()
        del self.messages[0]
        del self.names[0]


    def connectionLost(self, reason):
        """
        Close any open files when the connection is lost.

        @type reason: L{Failure <twisted.python.failure.Failure>}
        @param reason: The reason the connection was terminated.
        """
        if self.messages and self.messages[0][2]:
            self.messages[0][2].close()


    def _openFile(self, path):
        """
        Open a file.

        This function wraps opening files within the class for unit testing
        purposes.

        @type path: L{bytes}
        @param path: The path of a file to open.

        @rtype: L{file}
        @return: A file object.

        @raise IOError: When the file cannot be opened.
        """
        return FilePath(path).open()



class SMTPRelayer(RelayerMixin, smtp.SMTPClient):
    def __init__(self, messagePaths, *args, **kw):
        smtp.SMTPClient.__init__(self, *args, **kw)
        self.loadMessages(messagePaths)

class ESMTPRelayer(RelayerMixin, smtp.ESMTPClient):
    def __init__(self, messagePaths, *args, **kw):
        smtp.ESMTPClient.__init__(self, *args, **kw)
        self.loadMessages(messagePaths)
