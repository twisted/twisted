
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

import stat, os, socket, time, md5, string
from twisted.protocols import pop3, smtp
from twisted.persisted import dirdbm
from twisted.mail import mail


_n = 0

def _generateMaildirName():
    """utility function to generate a unique maildir name
    """
    global _n
    t = str(int(time.time()))
    s = socket.gethostname()
    p = os.getpid()
    _n = _n+1
    return '%s.%s_%s.%s' % (t, p, _n, s)


def initializeMaildir(dir):
    if not os.path.isdir(dir):
        os.mkdir(dir)
        for subdir in ['new', 'cur', 'tmp', '.Trash']:
            os.mkdir(os.path.join(dir, subdir))
        for subdir in ['new', 'cur', 'tmp']:
            os.mkdir(os.path.join(dir, '.Trash', subdir))
        # touch
        open(os.path.join(dir, '.Trash', 'maildirfolder'), 'w').close()


class AbstractMaildirDomain:
    """Abstract maildir-backed domain.
    """

    __implements__ = mail.IDomain

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

    def exists(self, user):
        """Check for existence of user in the domain
        """
        if self.userDirectory(user.dest.local) is not None:
            return defer.succeed(user)
        else:
            return defer.succeed(None)

    def startMessage(self, user):
        """Save a message for a given user
        """
        name, domain = user.dest.local, user.dest.domain
        dir = self.userDirectory(name)
        fname = _generateMaildirName()
        filename = os.path.join(dir, 'tmp', fname)
        fp = open(filename, 'w')
        fp.write("Delivered-To: %(name)s@%(domain)s\n" % vars())
        return mail.FileMessage(fp, filename, os.path.join(dir, 'new', fname))


class MaildirMailbox(pop3.Mailbox):
    """Implement the POP3 mailbox semantics for a Maildir mailbox
    """

    def __init__(self, path):
        """Initialize with name of the Maildir mailbox
        """
        self.path = path
        self.list = []
        self.deleted = {}
        initializeMaildir(path)
        for name in ('cur', 'new'):
            for file in os.listdir(os.path.join(path, name)):
                self.list.append(os.path.join(path, name, file))

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
        return os.stat(self.list[i])[stat.ST_SIZE]

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


class MaildirDirdbmDomain(AbstractMaildirDomain):
    """A Maildir Domain where membership is checked by a dirdbm file
    """

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

    def authenticateUserAPOP(self, user, magic, digest, domain):
        """Return Mailbox to valid APOP authentications

        Check the credentials, returning None if they are invalid
        or a MaildirMailbox if they are valid.
        """
        if not self.dbm.has_key(user):
            return None
        my_digest = md5.new(magic+self.dbm[user]).digest()
        my_digest = string.join(map(lambda x: "%02x"%ord(x), my_digest), '')
        if digest == my_digest:
            return MaildirMailbox(os.path.join(self.root, user))
        else:
            return None

    def authenticateUserPASS(self, username, password):
        if not self.dbm.has_key(username) or self.dbm[username] != password:
            return None
        return MaildirMailbox(os.path.join(self.root, username))
