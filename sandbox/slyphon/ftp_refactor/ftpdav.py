# this is the ftp-related stuff that doesn't belong in the protocol itself
# -- Cred Objects --

import os
import time
import string
import types
import re
from cStringIO import StringIO

# Twisted Imports
from twisted.internet import reactor, protocol, error, defer
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, ConsumerToProtocolAdapter
from twisted.cred import error, portal, checkers, credentials
from twisted import application, python
from twisted.python import failure, log, components

# import my sandbox ftp
import ftp

try:
    import pwd, grp
except ImportError:
    print "sorry, currently ftpdav only works with linux and linux variants"
    raise SystemExit("ftpdav doesn't do windows")

def _callWithDefault(default, _f, *_a, **_kw):
    try:
        return _f(*_a, **_kw)
    except KeyError:
        return default

def _memberGIDs(gid):
    """returns a list of all gid's that are a member of group with id
    """
    gr_mem = 3
    return grp.getgrgid(gid)[gr_mem]

def _testPermissions(uid, gid, spath, mode='r'):
    """checks to see if uid has proper permissions to access path with mode
    @param uid: numeric user id
    @type uid: int
    @param gid: numeric group id
    @type gid: int
    @param spath: the path on the server to test
    @type spath: string
    @param mode: 'r' or 'w' (read or write)
    @type mode: string
    @returns: a True if the uid can access path
    @rval: Boolean
    """
    import os.path as osp 
    import stat
    if mode not in ['r', 'w']:
        raise ValueError("mode argument must be 'r' or 'w'")
    
    readMasks = {'usr': stat.S_IRUSR, 'grp': stat.S_IRGRP, 'oth': stat.S_IROTH}
    writeMasks = {'usr': stat.S_IWUSR, 'grp': stat.S_IWGRP, 'oth': stat.S_IWOTH}
    modes = {'r': readMasks, 'w': writeMasks}
    log.msg('running _testPermissions')
    if osp.exists(spath):
        s = os.lstat(spath)
        if uid == 0:    # root is superman, can access everything
            log.msg('uid == root, can do anything!')
            return True
        elif modes[mode]['usr'] & s.st_mode > 0 and uid == s.st_uid:
            log.msg('usr has proper permissions')
            return True
        elif ((modes[mode]['grp'] & s.st_mode > 0) and 
                (gid == s.st_gid or gid in _memberGIDs(gid))):
            log.msg('grp has proper permissions')
            return True
        elif modes[mode]['oth'] & s.st_mode > 0:
            log.msg('oth has proper permissions')
            return True
    return False   

class AnonymousShell(object):
    """"""
    __implements__ = (ftp.IShell,)

    uid      = None        # uid of anonymous user for shell
    gid      = None        # gid of anonymous user for shell
    clientwd = '/'
    filepath = None

    def __init__(self, user=None, tld=None):
        """Constructor
        @param user: the name of the user whose permissions we'll be using
        @type user: string
        """
        self.user     = user        # user name
        self.tld      = tld
        self.debug    = True

        # TODO: self.user needs to be set to something!!!
        if self.user is None:
            uid = os.getuid()
            self.user = pwd.getpwuid(os.getuid())[0]
            self.getUserUIDAndGID()
        #if self.tld is not None:
            #self.filepath = python.FilePath(self.tld)

    def getUserUIDAndGID(self):
        """used to set up permissions checking. finds the uid and gid of 
        the shell.user. called during __init__
        """
        log.msg('getUserUIDAndGID')
        pw_name, pw_passwd, pw_uid, pw_gid, pw_dir = range(5)
        try:
            p = pwd.getpwnam(self.user)
            self.uid, self.gid = p[pw_uid], p[pw_gid]
            log.debug("set (uid,gid) for file-permissions checking to (%s,%s)" % (self.uid,self.gid))
        except KeyError, (e,):
            log.msg("""
COULD NOT SET ANONYMOUS UID! Name %s could not be found.
We will continue using the user %s.
""" % (self.user, pwd.getpwuid(os.getuid())[pw_name]))


    def pwd(self):
        return self.clientwd

    def myjoin(self, lpath, rpath):
        """does a dumb join between two path elements, ensuring
        there is only one '/' between them. pays no attention to the
        filesystem, unlike os.path.join
        
        @param lpath: path element to the left of the '/' in the result
        @type lpath: string
        @param rpath: path element to the right of the '/' in the result
        @type rpath: string
        """
        if lpath and lpath[-1] == os.sep:
            lpath = lpath[:-1]
        if rpath and rpath[0] == os.sep:
            rpath = rpath[1:]
        return "%s%s%s" % (lpath, os.sep, rpath)

    def mapCPathToSPath(self, rpath):
        if not rpath or rpath[0] != '/':      # if this is not an absolute path
            # add the clients working directory to the requested path
            mappedClientPath = self.myjoin(self.clientwd, rpath) 
        else:
            mappedClientPath = rpath
        # next add the client's top level directory to the requested path
        mappedServerPath = self.myjoin(self.tld, mappedClientPath)
        ncpath, nspath = os.path.normpath(mappedClientPath), os.path.normpath(mappedServerPath)
        common = os.path.commonprefix([self.tld, nspath])
        if common != self.tld:
            raise PathBelowTLDError('Cannot access below / directory')
        if not os.path.exists(nspath):
            raise FileNotFoundError(nspath)
        return (mappedClientPath, mappedServerPath)
 
    def cwd(self, path):
        cpath, spath = self.mapCPathToSPath(path)
        log.debug(cpath, spath)
        if os.path.exists(spath) and os.path.isdir(spath):
            self.clientwd = cpath
        else:
            raise FileNotFoundError(cpath)
       
    def cdup(self):
        self.cwd('..')

    def dele(self, path):
        raise AnonUserDeniedError()
        
    def mkd(self, path):
        raise AnonUserDeniedError()
        
    def rmd(self, path):
        raise AnonUserDeniedError()
 
    def retr(self, path):
        import os.path as osp
        cpath, spath = self.mapCPathToSPath(path)
        if not osp.isfile(spath):
            raise FileNotFoundError(cpath)
        #if not _testPermissions(self.uid, self.gid, spath):
            #raise PermissionDeniedError(cpath)
        try:
            return (file(spath, 'rb'), os.path.getsize(spath))
        except (IOError, OSError), (e,):
            log.debug(e)
            raise OperationFailedError('An error occurred %s' % e)

    def stor(self, params):
        raise AnonUserDeniedError()

    def getUnixLongListString(self, spath):
        """generates the equivalent output of a unix ls -l path, but
        using python-native code. 

        @param path: the path to return the listing for
        @type path: string
        @attention: this has only been tested on posix systems, I don't
            know at this point whether or not it will work on win32
        """
        import pwd, grp, time

        TYPE, PMSTR, NLINKS, OWN, GRP, SZ, MTIME, NAME = range(8)

        if os.path.isdir(spath):
            log.debug('list path isdir')
            dlist = os.listdir(spath)
            log.debug(dlist)
            dlist.sort()
        else:
            log.debug('list path is not dir')
            dlist = [spath]

        pstat = None
        result = []
        sio = StringIO()
        maxNameWidth, maxOwnWidth, maxGrpWidth, maxSizeWidth, maxNlinksWidth = 0, 0, 0, 0, 0
        

        for item in dlist:
            try:
                pstat = os.lstat(os.path.join(spath, item))

                # this is exarkun's bit of magic
                fmt = 'pld----'
                pmask = lambda mode: ''.join([mode & (256 >> n) and 'rwx'[n % 3] or '-' for n in range(9)])
                dtype = lambda mode: [fmt[i] for i in range(7) if (mode >> 12) & (1 << i)][0]

                type = dtype(pstat.st_mode)
                pmstr = pmask(pstat.st_mode)
                nlinks = str(pstat.st_nlink)
                owner = _callWithDefault([str(pstat.st_uid)], pwd.getpwuid, pstat.st_uid)[0]
                group = _callWithDefault([str(pstat.st_gid)], grp.getgrgid, pstat.st_gid)[0]
                size = str(pstat.st_size)
                mtime = time.strftime('%b %d %I:%M', time.gmtime(pstat.st_mtime))
                name = os.path.split(item)[1]
                unixpms = "%s%s" % (type,pmstr)
            except (OSError, KeyError), e:
                log.debug(e)
                continue
            if len(name) > maxNameWidth:
                maxNameWidth = len(name)
            if len(owner) > maxOwnWidth:
                maxOwnWidth = len(owner)
            if len(group) > maxGrpWidth:
                maxGrpWidth = len(group)
            if len(size) > maxSizeWidth:
                maxSizeWidth = len(size)
            if len(nlinks) > maxNlinksWidth:
                maxNlinksWidth = len(nlinks)
            result.append([type, pmstr, nlinks, owner, group, size, mtime, name])

        for r in result:
            r[OWN]  = r[OWN].ljust(maxOwnWidth)
            r[GRP]  = r[GRP].ljust(maxGrpWidth)
            r[SZ]   = r[SZ].rjust(maxSizeWidth)
            #r[NAME] = r[NAME].ljust(maxNameWidth)
            r[NLINKS] = r[NLINKS].rjust(maxNlinksWidth)
            sio.write('%s%s %s %s %s %s %8s %s\n' % tuple(r))

        sio.seek(0)
        return sio
       
    def list(self, path):
        cpath, spath = self.mapCPathToSPath(path)
        log.debug('cpath: %s,   spath:%s' % (cpath, spath))
        #if not _testPermissions(self.uid, self.gid, spath):
            #raise PermissionDeniedError(cpath)
        sio = self.getUnixLongListString(spath)
        return (sio, len(sio.getvalue()))

    def mdtm(self, path):
        from stat import ST_MTIME
        cpath, spath = self.mapCPathToSPath(path)
        if not os.path.isfile(spath):
            raise FileNotFoundError(spath)
        try:
            dtm = time.strftime("%Y%m%d%H%M%S", time.gmtime(os.stat(spath)[ST_MTIME]))
        except OSError, (e,):
            log.err(e)
            raise OperationFailedError(e)
        else:
            return dtm

    def size(self, path):
        """returns the size in bytes of path"""
        cpath, spath = self.mapCPathToSPath(path)
        if not os.path.isfile(spath):
            raise FileNotFoundError(spath)
        return os.path.getsize(spath)
   
    def nlist(self, path):
        raise CmdNotImplementedError()

class Shell(AnonymousShell):
    def dele(self, path):
        pass

    def mkd(self, path):
        pass

    def rmd(self, path):
        pass

    def stor(self, path):
        cpath, spath = self.mapCPathToSPath(path)
        if os.access(spath, os.W_OK):
            try:
                return file(spath, 'wb')
            except (IOError, OSError), (e,):
                log.debug(e)
                raise OperationFailedError('An error occurred %s' % e)
        raise PermissionDeniedError('Could not write file %s' % cpath)


class Realm:
    __implements__ = (portal.IRealm,)
    clientwd = '/'
    user = 'anonymous'
    logout = None
    tld = None          

    def __init__(self, tld=None, logout=None):
        """constructor
        @param tld: the top-level (i.e. root) directory on the server
        @type tld: string
        @attention: you *must* set tld somewhere before using the avatar!!
        @param logout: a special logout routine you want to be run when the user
            logs out (cleanup)
        @type logout: a function/method object
        """
        self.tld = tld
        self.logout = logout

    def requestAvatar(self, avatarId, mind, *interfaces):
        if ftp.IShell in interfaces:
            if self.tld is None:
                raise ftp.TLDNotSetInRealmError("you must set FTPRealm's tld to a non-None value before creating avatars!!!")
            avatar = AnonymousShell(user=self.user, tld=self.tld)
            avatar.clientwd = self.clientwd
            avatar.logout = self.logout
            return ftp.IShell, avatar, avatar.logout
        log.msg('interfaces %s' % interfaces)
        raise NotImplementedError("Only IShell interface is supported by this realm")


