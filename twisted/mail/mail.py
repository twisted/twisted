"""Mail support for twisted python.
"""


import stat, os, UserDict, socket, time, string, operator, md5, binascii, copy
from twisted.protocols import smtp, pop3, protocol
from twisted.persisted import dirdbm

class DomainBasedFactory(protocol.Factory):
    """A server for multiple mail domains.
    """
    def __init__(self, domains):
        self.domains = domains


class VirtualSMTPFactory(DomainBasedFactory):
    """A virtual SMTP server.
    """
    def buildProtocol(self, addr):
        p = smtp.DomainSMTPHandler()
        p.factory = self
        return p


class VirtualPOP3Factory(DomainBasedFactory):
    """A virtual POP3 server.
    """
    def buildProtocol(self, addr):
        p = pop3.VirtualPOP3()
        p.factory = self
        return p


class DomainWithDefaultDict:

    def __init__(self, domains, default):
        self.domains = domains
        self.default = default

    def has_key(self, name):
        return 1

    def __getitem__(self, name):
        return self.domains.get(name, self.default)



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
        """alwyas returns None.
        """
        return None

    def exists(self, name, domain):
        """ UNDOCUMENTED
        """
        return self.userDirectory(name) is not None

    def saveMessage(self, name, message, domain):
        """ UNDOCUMENTED
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


class BounceDomain:
    """ UNDOCUMENTED
    """
    def exists(self, name, domain):
        """ UNDOCUMENTED
        """
        return 0


class MaildirMailbox(pop3.Mailbox):
    """ UNDOCUMENTED
    """

    def __init__(self, path):
        """ UNDOCUMENTED
        """
        self.path = path
        self.list = []
        for name in ('cur', 'new'):
            for file in os.listdir(os.path.join(path, name)):
                self.list.append(os.path.join(path, name, file))

    def listMessages(self):
        """ UNDOCUMENTED
        """
        ret = []
        for mess in self.list:
            if mess:
                ret.append(os.stat(mess)[stat.ST_SIZE])
            else:
                ret.append(0)
        return ret

    def getMessage(self, i):
        """ UNDOCUMENTED
        """
        return open(self.list[i])

    def getUidl(self, i):
        """ UNDOCUMENTED
        """
        return os.path.basename(self.list[i])

    def deleteMessage(self, i):
        """ UNDOCUMENTED
        """
        os.rename(self.list[i], 
                  os.path.join(self.path,'del',os.path.basename(self.list[i])))
        self.list[i] = 0

    def getSubFolders(self):
        dirs = []
        for dir in os.path.listdir(self.path):
            if dir not in ['cur', 'new', 'del']:
                dirs.append(dir)
        return dirs


class MaildirDirdbmDomain(AbstractMaildirDomain):
    """ UNDOCUMENTED
    """

    def __init__(self, root, postmaster=0):
        """ UNDOCUMENTED
        """
        AbstractMaildirDomain.__init__(self, root)
        self.dbm = dirdbm.open(os.path.join(root, 'passwd'))
        self.postmaster = postmaster

    def userDirectory(self, name):
        """ UNDOCUMENTED
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
        """ UNDOCUMENTED
        """
        if not self.dbm.has_key(user):
            return None
        my_digest = md5.new(magic+self.dbm[user]).digest()
        my_digest = binascii.hexlify(my_digest)
        if digest == my_digest:
            return MaildirMailbox(os.path.join(self.root, user, 'inbox'))

    def getUserFolder(self, user, password, folder):
        if self.dbm.get(user) != password:
            return None
        return MaildirMailbox(os.path.join(self.root, user, folder))
