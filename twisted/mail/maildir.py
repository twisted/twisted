"""Mail support for twisted python.
"""

import stat, os, socket, time, md5, binascii
from twisted.protocols import pop3
from twisted.persisted import dirdbm

n = 0
def _generateMaildirName():
    """utility function to generate a unique maildir name
    """
    global n
    t = str(int(time.time()))
    s = socket.gethostname()
    p = os.getpid()
    n = n+1
    return '%s.%s_%s.%s' % (t, p, n, s)


class AbstractMaildirDomain:
    """Abstract maildir-backed domain.
    """
    def __init__(self, root):
        """Initialize.
        """
        self.root = root

    def userDirectory(self, user):
        """Get the maildir directory for a given user

        Override to specify where to save mails for users.
        Return None for non-existing users.
        """
        return None

    def exists(self, name, domain):
        """Check for existence of user in the domain
        """
        return self.userDirectory(name) is not None

    def saveMessage(self, origin, name, message, domain):
        """Save a message for a given user
        """
        dir = os.path.join(self.userDirectory(name), 'inbox')
        fname = _generateMaildirName() 
        filename = os.path.join(dir, 'new', fname)
        fp = open(filename, 'w')
        try:
            fp.write("Delivered-To: %(name)s@%(domain)s\n" % vars())
            fp.write(message)
        finally:
            fp.close()


class MaildirMailbox(pop3.Mailbox):
    """Implement the POP3 mailbox semantics for a Maildir mailbox
    """

    def __init__(self, path):
        """Initialize with name of the Maildir mailbox
        """
        self.path = path
        self.list = []
        for name in ('cur', 'new'):
            for file in os.listdir(os.path.join(path, name)):
                self.list.append(os.path.join(path, name, file))

    def listMessages(self):
        """Return a list of lengths of all files in new/ and cur/
        """
        ret = []
        for mess in self.list:
            if mess:
                ret.append(os.stat(mess)[stat.ST_SIZE])
            else:
                ret.append(0)
        return ret

    def getMessage(self, i):
        """Return an open file-pointer to a message
        """
        return open(self.list[i])

    def getUidl(self, i):
        """Return a unique identifier for a message

        This is done using the basename of the filename.
        It is globally unique because this is how Maildirs are designed.
        """
        return os.path.basename(self.list[i])

    def deleteMessage(self, i):
        """Delete a message

        This only moves a message to the del/ subdirectory,
        so it can be undeleted by an administrator.
        """
        os.rename(self.list[i], 
                  os.path.join(self.path,'del',os.path.basename(self.list[i])))
        self.list[i] = 0

    def getSubFolders(self):
        """ UNDOCUMENTED
        """
        dirs = []
        for dir in os.path.listdir(self.path):
            if dir not in ['cur', 'new', 'del']:
                dirs.append(dir)
        return dirs


class MaildirDirdbmDomain(AbstractMaildirDomain):
    """A Maildir Domain where membership is checked by a dirdbm file
    """

    def __init__(self, root, postmaster=0):
        """Initialize

        The first argument is where the Domain directory is rooted.
        The second is whether non-existing addresses are simply
        forwarded to postmaster instead of outright bounce

        The directory structure of a MailddirDirdbmDomain is:

        /passwd <-- a dirdbm file
        /USER/inbox/{cur,new,del} <-- each user has these three directories
        """
        AbstractMaildirDomain.__init__(self, root)
        self.dbm = dirdbm.open(os.path.join(root, 'passwd'))
        self.postmaster = postmaster

    def userDirectory(self, name):
        """Get the directory for a user

        If the user exists in the dirdbm file, return the directory
        os.path.join(root, name, 'inbox'), creating it if necessary.
        Otherwise, returns postmaster's mailbox instead if bounces
        go to postmaster, otherwise return None
        """
        if not self.dbm.has_key(name):
            if not self.postmaster:
                return None
            name = 'postmaster'
	dir = os.path.join(self.root, name)
        if not os.path.isdir(dir):
            os.mkdir(dir)
            os.mkdir(os.path.join(dir, 'inbox'))
            os.mkdir(os.path.join(dir, 'inbox', 'new'))
            os.mkdir(os.path.join(dir, 'inbox', 'cur'))
            os.mkdir(os.path.join(dir, 'inbox', 'del'))
        return dir

    def authenticateUserAPOP(self, user, magic, digest, domain):
        """Return Mailbox to valid APOP authentications

        Check the credentials, returning None if they are invalid
        or a MaildirMailbox if they are valid.
        """
        if not self.dbm.has_key(user):
            return None
        my_digest = md5.new(magic+self.dbm[user]).digest()
        my_digest = binascii.hexlify(my_digest)
        if digest == my_digest:
            return MaildirMailbox(os.path.join(self.root, user, 'inbox'))

    def getUserFolder(self, user, password, folder):
        """ UNDOCUMENTED
        """
        if self.dbm.get(user) != password:
            return None
        return MaildirMailbox(os.path.join(self.root, user, folder))
