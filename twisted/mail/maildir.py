# -*- test-case-name: twisted.mail.test.test_mail -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Maildir-style mailbox support
"""

from __future__ import generators

import os
import stat
import socket
import time
import md5
import cStringIO

from zope.interface import implements

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

from twisted.mail import pop3
from twisted.mail import smtp
from twisted.protocols import basic
from twisted.persisted import dirdbm
from twisted.python import log, failure
from twisted.mail import mail
from twisted.mail import alias
from twisted.internet import interfaces, defer, reactor

from twisted import cred
import twisted.cred.portal
import twisted.cred.credentials
import twisted.cred.checkers
import twisted.cred.error

INTERNAL_ERROR = '''\
From: Twisted.mail Internals
Subject: An Error Occurred

  An internal server error has occurred.  Please contact the
  server administrator.
'''

class _MaildirNameGenerator:
    """Utility class to generate a unique maildir name
    """
    n = 0
    p = os.getpid()
    s = socket.gethostname().replace('/', r'\057').replace(':', r'\072')

    def generate(self):
        self.n = self.n + 1
        t = time.time()
        seconds = str(int(t))
        microseconds = str(int((t-int(t))*10e6))
        return '%s.M%sP%sQ%s.%s' % (seconds, microseconds,
                                    self.p, self.n, self.s)

_generateMaildirName = _MaildirNameGenerator().generate

def initializeMaildir(dir):
    if not os.path.isdir(dir):
        os.mkdir(dir, 0700)
        for subdir in ['new', 'cur', 'tmp', '.Trash']:
            os.mkdir(os.path.join(dir, subdir), 0700)
        for subdir in ['new', 'cur', 'tmp']:
            os.mkdir(os.path.join(dir, '.Trash', subdir), 0700)
        # touch
        open(os.path.join(dir, '.Trash', 'maildirfolder'), 'w').close()


class MaildirMessage(mail.FileMessage):
    size = None

    def __init__(self, address, fp, *a, **kw):
        header = "Delivered-To: %s\n" % address
        fp.write(header)
        self.size = len(header)
        mail.FileMessage.__init__(self, fp, *a, **kw)

    def lineReceived(self, line):
        mail.FileMessage.lineReceived(self, line)
        self.size += len(line)+1

    def eomReceived(self):
        self.finalName = self.finalName+',S=%d' % self.size
        return mail.FileMessage.eomReceived(self)

class AbstractMaildirDomain:
    """Abstract maildir-backed domain.
    """
    alias = None
    root = None

    def __init__(self, service, root):
        """Initialize.
        """
        self.root = root

    def userDirectory(self, user):
        """Get the maildir directory for a given user

        Override to specify where to save mails for users.
        Return None for non-existing users.
        """
        return None

    ##
    ## IAliasableDomain
    ##

    def setAliasGroup(self, alias):
        self.alias = alias

    ##
    ## IDomain
    ##
    def exists(self, user, memo=None):
        """Check for existence of user in the domain
        """
        if self.userDirectory(user.dest.local) is not None:
            return lambda: self.startMessage(user)
        try:
            a = self.alias[user.dest.local]
        except:
            raise smtp.SMTPBadRcpt(user)
        else:
            aliases = a.resolve(self.alias, memo)
            if aliases:
                return lambda: aliases
            log.err("Bad alias configuration: " + str(user))
            raise smtp.SMTPBadRcpt(user)

    def startMessage(self, user):
        """Save a message for a given user
        """
        if isinstance(user, str):
            name, domain = user.split('@', 1)
        else:
            name, domain = user.dest.local, user.dest.domain
        dir = self.userDirectory(name)
        fname = _generateMaildirName()
        filename = os.path.join(dir, 'tmp', fname)
        fp = open(filename, 'w')
        return MaildirMessage('%s@%s' % (name, domain), fp, filename,
                              os.path.join(dir, 'new', fname))

    def willRelay(self, user, protocol):
        return False

    def addUser(self, user, password):
        raise NotImplementedError

    def getCredentialsCheckers(self):
        raise NotImplementedError
    ##
    ## end of IDomain
    ##

class _MaildirMailboxAppendMessageTask:
    implements(interfaces.IConsumer)

    osopen = staticmethod(os.open)
    oswrite = staticmethod(os.write)
    osclose = staticmethod(os.close)
    osrename = staticmethod(os.rename)

    def __init__(self, mbox, msg):
        self.mbox = mbox
        self.defer = defer.Deferred()
        self.openCall = None
        if not hasattr(msg, "read"):
            msg = StringIO.StringIO(msg)
        self.msg = msg
        # This is needed, as this startup phase might call defer.errback and zero out self.defer
        # By doing it on the reactor iteration appendMessage is able to use .defer without problems.
        reactor.callLater(0, self.startUp)

    def startUp(self):
        self.createTempFile()
        if self.fh != -1:
            self.filesender = basic.FileSender()
            self.filesender.beginFileTransfer(self.msg, self)

    def registerProducer(self, producer, streaming):
        self.myproducer = producer
        self.streaming = streaming
        if not streaming:
            self.prodProducer()

    def prodProducer(self):
        self.openCall = None
        if self.myproducer is not None:
            self.openCall = reactor.callLater(0, self.prodProducer)
            self.myproducer.resumeProducing()

    def unregisterProducer(self):
        self.myproducer = None
        self.streaming = None
        self.osclose(self.fh)
        self.moveFileToNew()

    def write(self, data):
        try:
            self.oswrite(self.fh, data)
        except:
            self.fail()

    def fail(self, err=None):
        if err is None:
            err = failure.Failure()
        if self.openCall is not None:
            self.openCall.cancel()
        self.defer.errback(err)
        self.defer = None

    def moveFileToNew(self):
        while True:
            newname = os.path.join(self.mbox.path, "new", _generateMaildirName())
            try:
                self.osrename(self.tmpname, newname)
                break
            except OSError, (err, estr):
                import errno
                # if the newname exists, retry with a new newname.
                if err != errno.EEXIST:
                    self.fail()
                    newname = None
                    break
        if newname is not None:
            self.mbox.list.append(newname)
            self.defer.callback(None)
            self.defer = None

    def createTempFile(self):
        attr = (os.O_RDWR | os.O_CREAT | os.O_EXCL
                | getattr(os, "O_NOINHERIT", 0)
                | getattr(os, "O_NOFOLLOW", 0))
        tries = 0
        self.fh = -1
        while True:
            self.tmpname = os.path.join(self.mbox.path, "tmp", _generateMaildirName())
            try:
                self.fh = self.osopen(self.tmpname, attr, 0600)
                return None
            except OSError:
                tries += 1
                if tries > 500:
                    self.defer.errback(RuntimeError("Could not create tmp file for %s" % self.mbox.path))
                    self.defer = None
                    return None

class MaildirMailbox(pop3.Mailbox):
    """Implement the POP3 mailbox semantics for a Maildir mailbox
    """
    AppendFactory = _MaildirMailboxAppendMessageTask

    def __init__(self, path):
        """Initialize with name of the Maildir mailbox
        """
        self.path = path
        self.list = []
        self.deleted = {}
        initializeMaildir(path)
        for name in ('cur', 'new'):
            for file in os.listdir(os.path.join(path, name)):
                self.list.append((file, os.path.join(path, name, file)))
        self.list.sort()
        self.list = [e[1] for e in self.list]

    def listMessages(self, i=None):
        """Return a list of lengths of all files in new/ and cur/
        """
        if i is None:
            ret = []
            for mess in self.list:
                if mess:
                    ret.append(os.stat(mess)[stat.ST_SIZE])
                else:
                    ret.append(0)
            return ret
        return self.list[i] and os.stat(self.list[i])[stat.ST_SIZE] or 0

    def getMessage(self, i):
        """Return an open file-pointer to a message
        """
        return open(self.list[i])

    def getUidl(self, i):
        """Return a unique identifier for a message

        This is done using the basename of the filename.
        It is globally unique because this is how Maildirs are designed.
        """
        # Returning the actual filename is a mistake.  Hash it.
        base = os.path.basename(self.list[i])
        return md5.md5(base).hexdigest()

    def deleteMessage(self, i):
        """Delete a message

        This only moves a message to the .Trash/ subfolder,
        so it can be undeleted by an administrator.
        """
        trashFile = os.path.join(
            self.path, '.Trash', 'cur', os.path.basename(self.list[i])
        )
        os.rename(self.list[i], trashFile)
        self.deleted[self.list[i]] = trashFile
        self.list[i] = 0

    def undeleteMessages(self):
        """Undelete any deleted messages it is possible to undelete

        This moves any messages from .Trash/ subfolder back to their
        original position, and empties out the deleted dictionary.
        """
        for (real, trash) in self.deleted.items():
            try:
                os.rename(trash, real)
            except OSError, (err, estr):
                import errno
                # If the file has been deleted from disk, oh well!
                if err != errno.ENOENT:
                    raise
                # This is a pass
            else:
                try:
                    self.list[self.list.index(0)] = real
                except ValueError:
                    self.list.append(real)
        self.deleted.clear()

    def appendMessage(self, txt):
        """Appends a message into the mailbox."""
        task = self.AppendFactory(self, txt)
        return task.defer

class StringListMailbox:
    implements(pop3.IMailbox)

    def __init__(self, msgs):
        self.msgs = msgs

    def listMessages(self, i=None):
        if i is None:
            return map(len, self.msgs)
        return len(self.msgs[i])

    def getMessage(self, i):
        return StringIO.StringIO(self.msgs[i])

    def getUidl(self, i):
        return md5.new(self.msgs[i]).hexdigest()

    def deleteMessage(self, i):
        pass

    def undeleteMessages(self):
        pass

    def sync(self):
        pass

class MaildirDirdbmDomain(AbstractMaildirDomain):
    """A Maildir Domain where membership is checked by a dirdbm file
    """

    implements(cred.portal.IRealm, mail.IAliasableDomain)

    portal = None
    _credcheckers = None

    def __init__(self, service, root, postmaster=0):
        """Initialize

        The first argument is where the Domain directory is rooted.
        The second is whether non-existing addresses are simply
        forwarded to postmaster instead of outright bounce

        The directory structure of a MailddirDirdbmDomain is:

        /passwd <-- a dirdbm file
        /USER/{cur,new,del} <-- each user has these three directories
        """
        AbstractMaildirDomain.__init__(self, service, root)
        dbm = os.path.join(root, 'passwd')
        if not os.path.exists(dbm):
            os.makedirs(dbm)
        self.dbm = dirdbm.open(dbm)
        self.postmaster = postmaster

    def userDirectory(self, name):
        """Get the directory for a user

        If the user exists in the dirdbm file, return the directory
        os.path.join(root, name), creating it if necessary.
        Otherwise, returns postmaster's mailbox instead if bounces
        go to postmaster, otherwise return None
        """
        if not self.dbm.has_key(name):
            if not self.postmaster:
                return None
            name = 'postmaster'
        dir = os.path.join(self.root, name)
        if not os.path.exists(dir):
            initializeMaildir(dir)
        return dir

    ##
    ## IDomain
    ##
    def addUser(self, user, password):
        self.dbm[user] = password
        # Ensure it is initialized
        self.userDirectory(user)

    def getCredentialsCheckers(self):
        if self._credcheckers is None:
            self._credcheckers = [DirdbmDatabase(self.dbm)]
        return self._credcheckers

    ##
    ## IRealm
    ##
    def requestAvatar(self, avatarId, mind, *interfaces):
        if pop3.IMailbox not in interfaces:
            raise NotImplementedError("No interface")
        if avatarId == cred.checkers.ANONYMOUS:
            mbox = StringListMailbox([INTERNAL_ERROR])
        else:
            mbox = MaildirMailbox(os.path.join(self.root, avatarId))

        return (
            pop3.IMailbox,
            mbox,
            lambda: None
        )

class DirdbmDatabase:
    implements(cred.checkers.ICredentialsChecker)

    credentialInterfaces = (
        cred.credentials.IUsernamePassword,
        cred.credentials.IUsernameHashedPassword
    )

    def __init__(self, dbm):
        self.dirdbm = dbm

    def requestAvatarId(self, c):
        if c.username in self.dirdbm:
            if c.checkPassword(self.dirdbm[c.username]):
                return c.username
        raise cred.error.UnauthorizedLogin()
