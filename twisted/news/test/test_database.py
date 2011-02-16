# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.news.database}.
"""

__metaclass__ = type

from email.Parser import Parser
from socket import gethostname

from twisted.trial.unittest import TestCase
from twisted.internet.defer import succeed
from twisted.mail.smtp import messageid
from twisted.news.database import Article, PickleStorage, NewsShelf



class ModerationTestsMixin:
    """
    Tests for the moderation features of L{INewsStorage} implementations.
    """
    def setUp(self):
        self._email = []


    def sendmail(self, smtphost, from_addr, to_addrs, msg,
                 senderDomainName=None, port=25):
        """
        Fake of L{twisted.mail.smtp.sendmail} which records attempts to send
        email and immediately pretends success.

        Subclasses should arrange for their storage implementation to call this
        instead of the real C{sendmail} function.
        """
        self._email.append((
                smtphost, from_addr, to_addrs, msg, senderDomainName, port))
        return succeed(None)


    _messageTemplate = """\
From: some dude
To: another person
Subject: activities etc
Message-ID: %(articleID)s
Newsgroups: %(newsgroup)s
%(approved)s
Body of the message is such.
""".replace('\n', '\r\n')


    def getApprovedMessage(self, articleID, group):
        """
        Return a C{str} containing an RFC 2822 formatted message including an
        I{Approved} header indicating it has passed through moderation.
        """
        return self._messageTemplate % {
            'articleID': articleID,
            'newsgroup': group,
            'approved': 'Approved: yup\r\n'}


    def getUnapprovedMessage(self, articleID, group):
        """
        Return a C{str} containing an RFC 2822 formatted message with no
        I{Approved} header indicating it may require moderation.
        """
        return self._messageTemplate % {
            'articleID': articleID,
            'newsgroup': group,
            'approved': '\r\n'}


    def getStorage(self, groups, moderators, mailhost, sender):
        """
        Override in a subclass to return a L{INewsStorage} provider to test for
        correct moderation behavior.

        @param groups: A C{list} of C{str} naming the groups which should exist
            in the resulting storage object.

        @param moderators: A C{dict} mapping C{str} each group name to a C{list}
            of C{str} giving moderator email (RFC 2821) addresses.
        """
        raise NotImplementedError()


    def test_postApproved(self):
        """
        L{INewsStorage.postRequest} posts the message if it includes an
        I{Approved} header.
        """
        group = "example.group"
        moderator = "alice@example.com"
        mailhost = "127.0.0.1"
        sender = "bob@example.org"
        articleID = messageid()
        storage = self.getStorage(
            [group], {group: [moderator]}, mailhost, sender)
        message = self.getApprovedMessage(articleID, group)
        result = storage.postRequest(message)

        def cbPosted(ignored):
            self.assertEquals(self._email, [])
            exists = storage.articleExistsRequest(articleID)
            exists.addCallback(self.assertTrue)
            return exists
        result.addCallback(cbPosted)
        return result


    def test_postModerated(self):
        """
        L{INewsStorage.postRequest} forwards a message to the moderator if it
        does not include an I{Approved} header.
        """
        group = "example.group"
        moderator = "alice@example.com"
        mailhost = "127.0.0.1"
        sender = "bob@example.org"
        articleID = messageid()
        storage = self.getStorage(
            [group], {group: [moderator]}, mailhost, sender)
        message = self.getUnapprovedMessage(articleID, group)
        result = storage.postRequest(message)

        def cbModerated(ignored):
            self.assertEquals(len(self._email), 1)
            self.assertEquals(self._email[0][0], mailhost)
            self.assertEquals(self._email[0][1], sender)
            self.assertEquals(self._email[0][2], [moderator])
            self._checkModeratorMessage(
                self._email[0][3], sender, moderator, group, message)
            self.assertEquals(self._email[0][4], None)
            self.assertEquals(self._email[0][5], 25)
            exists = storage.articleExistsRequest(articleID)
            exists.addCallback(self.assertFalse)
            return exists
        result.addCallback(cbModerated)
        return result


    def _checkModeratorMessage(self, messageText, sender, moderator, group, postingText):
        p = Parser()
        msg = p.parsestr(messageText)
        headers = dict(msg.items())
        del headers['Message-ID']
        self.assertEquals(
            headers,
            {'From': sender,
             'To': moderator,
             'Subject': 'Moderate new %s message: activities etc' % (group,),
             'Content-Type': 'message/rfc822'})

        posting = p.parsestr(postingText)
        attachment = msg.get_payload()[0]

        for header in ['from', 'to', 'subject', 'message-id', 'newsgroups']:
            self.assertEquals(posting[header], attachment[header])

        self.assertEquals(posting.get_payload(), attachment.get_payload())



class PickleStorageTests(ModerationTestsMixin, TestCase):
    """
    Tests for L{PickleStorage}.
    """
    def getStorage(self, groups, moderators, mailhost, sender):
        """
        Create and return a L{PickleStorage} instance configured to require
        moderation.
        """
        storageFilename = self.mktemp()
        storage = PickleStorage(
            storageFilename, groups, moderators, mailhost, sender)
        storage.sendmail = self.sendmail
        self.addCleanup(PickleStorage.sharedDBs.pop, storageFilename)
        return storage



class NewsShelfTests(ModerationTestsMixin, TestCase):
    """
    Tests for L{NewsShelf}.
    """
    def getStorage(self, groups, moderators, mailhost, sender):
        """
        Create and return a L{NewsShelf} instance configured to require
        moderation.
        """
        storageFilename = self.mktemp()
        shelf = NewsShelf(mailhost, storageFilename, sender)
        for name in groups:
            shelf.addGroup(name, 'm') # Dial 'm' for moderator
            for address in moderators.get(name, []):
                shelf.addModerator(name, address)
        shelf.sendmail = self.sendmail
        return shelf


    def test_notifyModerator(self):
        """
        L{NewsShelf.notifyModerator} sends a moderation email to a single
        moderator.
        """
        shelf = NewsShelf('example.com', self.mktemp(), 'alice@example.com')
        shelf.sendmail = self.sendmail
        shelf.notifyModerator('bob@example.org', Article('Foo: bar', 'Some text'))
        self.assertEquals(len(self._email), 1)


    def test_defaultSender(self):
        """
        If no sender is specified to L{NewsShelf.notifyModerators}, a default
        address based on the system hostname is used for both the envelope and
        RFC 2822 sender addresses.
        """
        shelf = NewsShelf('example.com', self.mktemp())
        shelf.sendmail = self.sendmail
        shelf.notifyModerators(['bob@example.org'], Article('Foo: bar', 'Some text'))
        self.assertEquals(self._email[0][1], 'twisted-news@' + gethostname())
        self.assertIn('From: twisted-news@' + gethostname(), self._email[0][3])
