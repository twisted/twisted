# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
import struct, array, pwd, os, stat, time, errno

from twisted.internet import defer, protocol

from common import NS, getNS


class FileTransferBase(protocol.Protocol):
    
    versions = (3, )

    def __init__(self):
        self.buf = ''
        otherVersion = None # this gets set
    
    def sendPacket(self, kind, data):
        self.transport.write(struct.pack('!LB', len(data)+1, kind) + data)

    def dataReceived(self, data):
        self.buf += data
        while len(self.buf) > 5:
            length, kind = struct.unpack('!LB', self.buf[:5])
            if len(self.buf) < 4 + length:
                return
            data, self.buf = self.buf[5:4+length], self.buf[4+length:]
            packetType = self.packetTypes.get(kind, None)
            if not packetType:
                print 'no packet type for', kind
                #XXX error
            f = getattr(self, 'packet_%s' % packetType, None)
            if not f:
                print 'not implemented', packetType
                return
                #XXX not implemented
            f(data)

    def _parseAttributes(self, data):
        flags = struct.unpack('!L', data[:4])[0]
        attrs = {} 
        data = data[4:]
        if flags & FILEXFER_ATTR_SIZE == FILEXFER_ATTR_SIZE:
            size = struct.unpack('!Q', data[:8])[0]
            attrs['size'] = size
            data = data[8:]
        if flags & FILEXFER_ATTR_OWNERGROUP == FILEXFER_ATTR_OWNERGROUP:
            uid, gid = struct.unpack('!2L', data[:8])
            attrs['uid'] = uid
            attrs['gid'] = gid
            data = data[8:]   
        if flags & FILEXFER_ATTR_PERMISSIONS == FILEXFER_ATTR_PERMISSIONS:
            perms = struct.unpack('!L', data[:4])[0]
            attrs['permissions'] = perms
            data = data[4:]
        if flags & FILEXFER_ATTR_ACMODTIME == FILEXFER_ATTR_ACMODTIME:
            atime, mtime = struct.unpack('!2L', data[:8])
            attrs['atime'] = atime
            attrs['mtime'] = mtime
            data = data[8:]
        if flags & FILEXFER_ATTR_EXTENDED == FILEXFER_ATTR_EXTENDED:
            extended_count = struct.unpack('!L', data[4:])[0]
            data = data[4:]
            for i in xrange(extended_count):
                extended_type, data = common.getNS(data)
                extended_data, data = common.getNS(data)
                print 'ext', extended_type, extended_data
                attrs['ext_%s' % extended_type] = extended_data
        return attrs, data

    def _packAttributes(self, attrs):
        flags = 0
        data = ''
        if 'size' in attrs:
            data += struct.pack('!Q', attrs['size'])
            flags |= FILEXFER_ATTR_SIZE
        if 'uid' in attrs and 'gid' in attrs:
            data += struct.pack('!2L', attrs['uid'], attrs['gid'])
            flags |= FILEXFER_ATTR_OWNERGROUP
        if 'permissions' in attrs:
            data += struct.pack('!L', attrs['permissions'])
            flags |= FILEXFER_ATTR_PERMISSIONS
        if 'atime' in attrs and 'mtime' in attrs:
            data += struct.pack('!2L', attrs['atime'], attrs['mtime'])
            flags |= FILEXFER_ATTR_ACMODTIME
        extended = []
        for k in attrs:
            if k.startswith('ext_'):
                ext_type = common.NS(k[4:])
                ext_data = common.NS(attrs[k])
                extended.append(ext_type+ext_data)
        if extended:
            data += struct.pack('!L', len(extended))
            data += ''.join(extended)
            flags |= FILEXFER_ATTR_EXTENDED
        return struct.pack('!L', flags) + data

class FileTransferServer(FileTransferBase):

    def __init__(self, avatar):
        FileTransferBase.__init__(self)
        self.avatar = avatar
        self.openFiles = {}
        self.openDirs = {}

    def packet_INIT(self, data):
        version = struct.unpack('!L', data[:4])[0]
        self.version = min(list(self.versions) + [version])
        data = data[4:]
        ext = {}
        while data:
            ext_name, data = getNS(data)
            ext_data, data = getNS(data)
            ext[ext_name] = ext_data
        our_ext = self.gotVersion(version, ext)
        our_ext_data = ""
        for (k,v) in our_ext.items():
            our_ext_data += NS(k) + NS(v)
        self.sendPacket(FXP_VERSION, struct.pack('!L', self.version) + \
                                     our_ext_data)

    def packet_OPEN(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        filename, data = getNS(data)
        flags, data = struct.unpack('!L', data[:4])[0], data[4:]
        attrs, data = self._parseAttributes(data)
        assert data == '', 'still have data in OPEN: %s' % repr(data)
        d = defer.maybeDeferred(self.openFile, filename, flags, attrs)
        d.addCallback(self._cbOpenFile, requestId)
        d.addErrback(self._ebStatus, requestId, "open failed")

    def _cbOpenFile(self, fileObj, requestId):
        fileId = str(id(fileObj))
        if fileId in self.openFiles:
            raise KeyError, 'id already open'
        self.openFiles[fileId] = fileObj
        self.sendPacket(FXP_HANDLE, struct.pack('!L', requestId) + NS(fileId))

    def packet_CLOSE(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        handle, data = getNS(data)
        assert data == '', 'still have data in CLOSE: %s' % repr(data)
        if handle in self.openFiles:
            fileObj = self.openFiles[handle]
            d = defer.maybeDeferred(self.closeFile, fileObj)
            d.addCallback(self._cbClose, handle, requestId)
            d.addErrback(self._ebStatus, requestId, "close failed")
        elif handle in self.openDirs:
            dirObj = self.openDirs[handle]
            d = defer.maybeDeferred(self.closeDirectory, dirObj)
            d.addCallback(self._cbClose, handle, requestId, 1)
            d.addErrback(self._ebStatus, requestId, "close failed")
        else:
            self._ebClose(failure.Failure(KeyError()), requestId)

    def _cbClose(self, result, handle, requestId, isDir = 0):
        if isDir:
            del self.openDirs[handle]
        else:
            del self.openFiles[handle]
        self._sendStatus(requestId, FX_OK, 'file closed')

    def packet_READ(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        handle, data = getNS(data)
        (offset, length), data = struct.unpack('!QL', data[:12]), data[12:]
        assert data == '', 'still have data in READ: %s' % repr(data)
        if handle not in self.openFiles:
            self._ebRead(failure.Failure(KeyError()), requestId)
        else:
            fileObj = self.openFiles[handle]
            d = defer.maybeDeferred(self.readFile, fileObj, offset, length)
            d.addCallback(self._cbRead, requestId)
            d.addErrback(self._ebStatus, requestId, "read failed")

    def _cbRead(self, result, requestId):
        if result == '': # python's read will return this for EOF
            raise EOFError()
        self.sendPacket(FXP_DATA, struct.pack('!L', requestId) + NS(result))

    def packet_WRITE(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        handle, data = getNS(data)
        offset, data = struct.unpack('!Q', data[:8])[0], data[8:]
        writeData, data = getNS(data)
        assert data == '', 'still have data in WRITE: %s' % repr(data)
        if handle not in self.openFiles:
            self._ebWrite(failure.Failure(KeyError()), requestId)
        else:
            fileObj = self.openFiles[handle]
            d = defer.maybeDeferred(self.writeFile, fileObj, offset, writeData)
            d.addCallback(self._cbStatus, requestId, "write succeeded")
            d.addErrback(self._ebStatus, requestId, "write failed")

    def packet_REMOVE(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        filename, data = getNS(data)
        assert data == '', 'still have data in REMOVE: %s' % repr(data)
        d = defer.maybeDeferred(self.removeFile, filename)
        d.addCallback(self._cbStatus, requestId, "remove succeeded")
        d.addErrback(self._ebStatus, requestId, "remove failed")

    def packet_RENAME(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        oldPath, data = getNS(data)
        newPath, data = getNS(data)
        assert data == '', 'still have data in RENAME: %s' % repr(data)
        d = defer.maybeDeferred(self.renameFile, oldPath, newPath)
        d.addCallback(self._cbStatus, requestId, "rename succeeded")
        d.addErrback(self._ebStatus, requestId, "rename failed")

    def packet_MKDIR(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        path, data = getNS(data)
        attrs, data = self._parseAttributes(data)
        assert data == '', 'still have data in MKDIR: %s' % repr(data)
        d = defer.maybeDeferred(self.makeDirectory, path, attrs)
        d.addCallback(self._cbStatus, requestId, "mkdir succeeded")
        d.addErrback(self._ebStatus, requestId, "mkdir failed")

    def packet_RMDIR(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        path, data = getNS(data)
        assert data == '', 'still have data in RMDIR: %s' % repr(data)
        d = defer.maybeDeferred(self.removeDirectory, path)
        d.addCallback(self._cbStatus, requestId, "rmdir succeeded")
        d.addErrback(self._ebStatus, requestId, "rmdir failed")

    def packet_OPENDIR(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        path, data = getNS(data)
        assert data == '', 'still have data in OPENDIR: %s' % repr(data)
        d = defer.maybeDeferred(self.openDirectory, path)
        d.addCallback(self._cbOpenDirectory, requestId)
        d.addErrback(self._ebStatus, requestId, "opendir failed")

    def _cbOpenDirectory(self, dirObj, requestId):
        handle = str(id(dirObj))
        if handle in self.openDirs:
            raise KeyError, "already opened this directory"
        self.openDirs[handle] = dirObj
        self.sendPacket(FXP_HANDLE, struct.pack('!L', requestId) + NS(handle))

    def packet_READDIR(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        handle, data = getNS(data)
        assert data == '', 'still have data in READDIR: %s' % repr(data)
        if handle not in self.openDirs:
            self._ebStatus(failure.Failure(KeyError()), requestId)
        else:
            dirObj = self.openDirs[handle]
            d = defer.maybeDeferred(self.scanDirectory, dirObj)
            d.addCallback(self._cbScanDirectory, requestId)
            d.addErrback(self._ebStatus, requestId, "scan directory failed")

    def _cbScanDirectory(self, result, requestId):
        data = struct.pack('!2L', requestId, len(result))
        for (filename, longname, attrs) in result:
            data += NS(filename)
            data += NS(longname)
            data += self._packAttributes(attrs)
        self.sendPacket(FXP_NAME, data)

    def packet_STAT(self, data, followLinks = 1):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        path, data = getNS(data)
        assert data == '', 'still have data in STAT/LSTAT: %s' % repr(data)
        d = defer.maybeDeferred(self.getAttrs, path, followLinks)
        d.addCallback(self._cbStat, requestId)
        d.addErrback(self._ebStatus, requestId, 'stat/lstat failed')

    def packet_LSTAT(self, data):
        self.packet_STAT(data, 0)

    def packet_FSTAT(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        handle, data = getNS(data)
        assert data == '', 'still have data in FSTAT: %s' % repr(data)
        if handle not in self.openDirs:
            self._ebStatus(failure.Failure(KeyError()), requestId)
        else:
            dirObj = self.openDirs[handle]
            d = defer.maybeDeferred(self.getAttrsOpaque, dirObj)
            d.addCallback(self._cbStat, requestId)
            d.addErrback(self._ebStatus, requestId, 'fstat failed')

    def _cbStat(self, result, requestId):
        data = struct.pack('!L', requestId) + self._packAttributes(result)
        self.sendPacket(FXP_ATTRS, data)

    def packet_SETSTAT(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        path, data = getNS(data)
        attrs, data = self._parseAttributes(data)
        assert data == '', 'still have data in SETSTAT: %s' % repr(data)
        d = defer.maybeDeferred(self.setAttrs, path, attrs)
        d.addCallback(self._cbStatus, requestId, 'setstat succeeded')
        d.addErrback(self._ebStatus, requestId, 'setstat failed')

    def packet_FSETSTAT(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        handle, data = getNS(data)
        attrs, data = self._parseAttributes(data)
        assert data == '', 'still have data in FSETSTAT: %s' % repr(data)
        if handle not in self.openFiles:
            self._ebStatus(failure.Failure(KeyError()), requestId)
        else:
            fileObj = self.openFiles[handle]
            d = defer.maybeDeferred(self.setAttrsOpaque, fileObj, attrs)
            d.addCallback(self._cbStatus, requestId, 'fsetstat succeeded')
            d.addErrback(self._ebStatus, requestId, 'fsetstat failed')

    def packet_READLINK(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        path, data = getNS(data)
        assert data == '', 'still have data in READLINK: %s' % repr(data)
        d = defer.maybeDeferred(self.readLink, path)
        d.addCallback(self._cbReadLink, requestId)
        d.addErrback(self._ebStatus, requestId, 'readlink failed')

    def _cbReadLink(self, result, requestId):
        self._cbScanDirectory([(result, '', {})], requestId)

    def packet_SYMLINK(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        linkPath, data = getNS(data)
        targetPath, data = getNS(data)
        d = defer.maybeDeferred(self.makeLink, linkPath, targetPath)
        d.addCallback(self._cbStatus, requestId, 'symlink succeeded')
        d.addErrback(self._ebStatus, requestId, 'symlink failed')

    def packet_REALPATH(self, data):
        requestId, data = struct.unpack('!L', data[:4])[0], data[4:]
        path, data = getNS(data)
        assert data == '', 'still have data in REALPATH: %s' % repr(data)
        d = defer.maybeDeferred(self.realPath, path)
        d.addCallback(self._cbReadLink, requestId) # same return format
        d.addErrback(self._ebStatus, requestId, 'realpath failed')
        
    def _cbStatus(self, result, requestId, msg = "request succeeded"):
        self._sendStatus(requestId, FX_OK, msg)

    def _ebStatus(self, reason, requestId, msg = "request failed"):
        print reason
        code = FX_FAILURE
        message = msg
        if reason.type in (IOError, OSError):
            if reason.value.errno == errno.ENOENT: # no such file
                code = FX_NO_SUCH_FILE
                message = reason.value.strerror
            elif reason.value.errno == errno.EACCES: # permission denied
                code = FX_PERMISSION_DENIED
                message = reason.value.strerror
        elif reason.type == EOFError: # EOF
            code = FX_EOF
            if reason.value.args:
                message = reason.value.args[0]
        elif reason.type == SFTPError:
            code = reason.value.code
            message = reason.value.message
        self._sendStatus(requestId, code, message)

    def _sendStatus(self, requestId, code, message, lang = ''):
        """
        Helper method to send a FXP_STATUS message.
        """
        data = struct.pack('!2L', requestId, code)
        data += NS(message)
        data += NS(lang)
        self.sendPacket(FXP_STATUS, data)

    def _runAsUser(self, f, *args):
        euid = os.geteuid()
        egid = os.getegid()
        uid, gid = self.avatar.getUserGroupId()
        os.setegid(gid)
        os.seteuid(uid)
        try:
            if not hasattr(f,'__iter__'):
                f = [(f, ) + args]
            for i in f:
                r = i[0](*i[1:])
        except:
            os.setegid(egid)
            os.seteuid(euid)
            raise
        else:
            os.setegid(egid)
            os.seteuid(euid)
            return r

    def _setAttrs(self, path, attrs):
        """
        NOTE: this function assumes it is runner as the logged-in user:
        i.e. under _runAsUser()
        """
        if attrs.has_key("uid") and attrs.has_key("gid"):
            os.lchown(path, attrs["uid"], attrs["gid"])
        if attrs.has_key("permissions"):
            os.chmod(path, attrs["permissions"])
        if attrs.has_key("atime") and attrs.has_key("mtime"):
            os.utime(path, (attrs["atime"]. attrs["mtime"]))

    def _getAttrs(self, s):
        return {
            "size" : s.st_size,
            "uid" : s.st_uid,
            "gid" : s.st_gid,
            "permissions" : s.st_mode,
            "atime" : s.st_atime,
            "mtime" : s.st_mtime
        }

    def _absPath(self, path):
        uid, gid = self.avatar.getUserGroupId()
        home = pwd.getpwuid(uid)[5] 
        return os.path.abspath(os.path.join(home, path))
        
    def gotVersion(self, otherVersion, extData):
        """
        Called when the client sends their version info.

        otherVersion is an integer representing the version of the SFTP
        protocol they are claiming.
        extData is a dictionary of extended_name : extended_data items.
        These items are sent by the client to indicate additional features.

        This method should return a dictionary of extended_name : extended_data
        items.  These items are the additional features (if any) supported
        by the server.
        """
        return {}

    def openFile(self, filename, flags, attrs):
        """
        Called when the clients asks to open a file.

        filename is a string representing the file to open.

        flags is a integer of the flags to open the file with, ORed together.
        The flags and their values are listed at the bottom of this file.
        
        attrs is a list of attributes to open the file with.  It is a
        dictionary, consisting of 0 or more keys.  The possible keys are:
            size: the size of the file in bytes
            uid: the user ID of the file as an integer
            gid: the group ID of the file as an integer
            permissions: the permissions of the file with as an integer.
            the bit representation of this field is defined by POSIX.
            atime: the access time of the file as seconds since the epoch.
            mtime: the modification time of the file as seconds since the epoch.
            ext_*: extended attributes.  The server is not required to
            understand this, but it may.

        NOTE: there is no way to indicate text or binary files.  it is up
        to the SFTP client to deal with this.

        This method returns an opaque identifier for this file.  This
        identifier is passed as the first argument to the other file
        access methods.  Alternatively, it can return a Deferred that will
        be called back with the identifier.

        The only requirement on the opaque identifier is that it is usable
        as the value in a directory.  Opening the same file twice should not
        return the same opaque identifer, and the identifier should last
        as long as it is open, or until the end of the client connection.
        """
        openFlags = 0
        if flags & FXF_READ == FXF_READ and flags & FXF_WRITE == 0:
            openFlags = os.O_RDONLY
        if flags & FXF_WRITE == FXF_WRITE and flags & FXF_READ == 0:
            openFlags = os.O_WRONLY
        if flags & FXF_WRITE == FXF_WRITE and flags & FXF_READ == FXF_READ:
            openFlags = os.O_RDWR
        if flags & FXF_APPEND == FXF_APPEND:
            openFlags |= os.O_APPEND
        if flags & FXF_CREAT == FXF_CREAT:
            openFlags |= os.O_CREAT
        if flags & FXF_TRUNC == FXF_TRUNC:
            openFlags |= os.O_TRUNC
        if flags & FXF_EXCL == FXF_EXCL:
            openFlags |= os.O_EXCL
        if attrs.has_key("permissions"):
            mode = attrs["permissions"]
            del attrs["permissions"]
        else:
            mode = 0777
        filename = self._absPath(filename)
        fd = self._runAsUser(os.open, filename, openFlags, mode)
        if attrs:
            self._runAsUser(self._setAttrs, filename, attrs)
        return fd

    def closeFile(self, opaqueId):
        """
        Close the file represented by the opaqueId.

        This method returns nothing if the close succeeds immediatly, or a 
        Deferred that is called back when the close succeeds.
        """
        return self._runAsUser(os.close, opaqueId)
    
    def readFile(self, opaqueId, offset, length):
        """
        Read from the file represented by the opaqueId.

        offset is an integer that is the index to start from in the file.
        length is the maximum length of data to return.  The actual amount
        returned may less than this.  For normal disk files, however,
        this should read the requested number (up to the end of the file).

        If EOF is reached before any data is read, raise EOFError.

        This method returns the data as a string, or a Deferred that is
        called back with same.
        """
        return self._runAsUser([(os.lseek, opaqueId, offset, 0),
                                (os.read, opaqueId, length)])

    def writeFile(self, opaqueId, offset, data):
        """
        Write to the file represented by the opaqueId
        
        offset is an integer that is the index to start from in the file.
        data is a string that is the data to write.

        This method returns when the write completes, or a Deferred that is
        called when it completes.
        """
        return self._runAsUser([(os.lseek, opaqueId, offset, 0),
                                (os.write, opaqueId, data)])

    def removeFile(self, filename):
        """
        Remove the given file.

        filename is the name of the file as a string.

        This method returns when the remove succeeds, or a Deferred that is
        called back when it succeeds.
        """
        filename = self._absPath(filename)
        return self._runAsUser(os.remove, filename)

    def renameFile(self, oldpath, newpath):
        """
        Rename the given file.

        oldpath is the current location of the file.
        newpath is the new file name.

        This method returns when the rename succeeds, or a Deferred that is
        called back when it succeeds.
        """
        oldpath = self._absPath(oldpath)
        newpath = self._absPath(newpath)
        return self._runAsUser(os.rename, oldpath, newpath)

    def makeDirectory(self, path, attrs):
        """
        Make a directory.

        path is the name of the directory to create as a string.
        attrs is a dictionary of attributes to create the directory with.
        It's meaning is the same as the attrs in the openFile method.

        This method returns when the directory is created, or a Deferred that
        is called back when it is created.
        """
        path = self._absPath(path)
        return self._runAsUser([(os.mkdir, path),
                                (self._setAttrs, path, attrs)])
    
    def removeDirectory(self, path):
        """
        Remove a directory (non-recursively)

        path is the directory to remove.

        It is an error to remove a directory that has files or directories in
        it.

        This method returns when the directory is removed, or a Deferred that
        is called back when it is removed.
        """
        path = self._absPath(path)
        self._runAsUser(os.rmdir, path)

    def openDirectory(self, path):
        """
        Open a directory for scanning.

        path is the directory to open.

        This method returns an opaqueId that is passed as the first argument
        to scanDirectory, or a Deferred that is called back with same.
        """
        return [self._absPath(path)]

    def scanDirectory(self, opaqueId):
        """
        Scan the directory represented by the opaqueId.

        This method returns a sequence of sequences of (filename, longname,
        attrs) or a Deferred of same.  This does not need to be all the files
        in the directory, but calls to this method should not return files
        returned by previous calls.  The container sequence must support
        __len__ and be iterable, but otherwise may be any other "sequence-like"
        object.  The interior sequences must support __getitem__, but
        otherwise may be any "sequence-like" object.

        filename is the name of the file relative to the directory.
        logname is an expanded format of the filename.  The recommended format
        is:
        -rwxr-xr-x   1 mjos     staff      348911 Mar 25 14:29 t-filexfer
        1234567890 123 12345678 12345678 12345678 123456789012

        The first line is sample output, the second is the length of the field.
        The fields are: permissions, link count, user owner, group owner,
        size in bytes, modification time.

        attrs is a dictionary in the format of the attrs argument to openFile.

        NOTE:  the way this works is the client sends a request,
        SSH_FXP_READDIR.  This method is called once for each request, and
        returns the files that this method returns.  The client keeps
        sending requests, and this method is called, until this method
        sends an exception (typically EOFError) to indicate that there are no
        more files in that directory.  Then, the client knows to stop sending
        requests.
        """
        if len(opaqueId) > 1: raise EOFError
        path = opaqueId[0]
        files = []
        for f in self._runAsUser(os.listdir, path):
            s = self._runAsUser(os.lstat, os.path.join(path, f))
            longname = _lsLine(f, s)
            attrs = self._getAttrs(s)
            files.append((f, longname, attrs))
        opaqueId.append(1)
        return files

    def closeDirectory(self, opaqueId):
        """
        Close the directory referenced by the opaqueId.

        This method returns when the directory is closed, or a Deferred that
        is called back when it is closed.
        """
        return

    def getAttrs(self, path, followLinks):
        """
        Return the attributes for the given path.

        path is the path to return attributes for as a string.
        followLinks is a boolean.  if it is True, follow symbolic links
        and return attributes for the real path at the base.  if it is False,
        return attributes for the specified path.

        This method returns a dictionary in the same format as the attrs
        argument to openFile or a Deferred that is called back with same.
        """
        path = self._absPath(path)
        if followLinks:
            s = self._runAsUser(os.stat, path)
        else:
            s = self._runAsUser(os.lstat, path)
        return self._getAttrs(s)

    def getAttrsOpaque(self, opaqueId):
        """
        Return the attributes for the given opaqueId.

        This method returns a dictionary in the same format as the attrs
        argument to openFile or a Deferred that is called back with same.
        """
        s = self._runAsUser(os.fstat, opaqueId)
        return self._getAttrs(s)

    def setAttrs(self, path, attrs):
        """
        Set the attributes for the path.

        path is the path to set attributes for as a string.
        attrs is a idctionary in the same format as the attrs argument to
        openFile.
        
        This method returns when the attributes are set or a Deferred that is 
        called back when they are.
        """
        path = self._absPath(path)
        self._runAsUser(self._setAttrs, path, attrs)

    def setAttrsOpaque(self, opaqueId, attrs):
        """
        Set the attributes for the opaqueId.

        attrs is a dictionary in the same format as the attrs argument to
        openFile.

        This method returns when the attributes are set or a Deferred that is
        called back when they are.
        """
        raise NotImplementedError 

    def readLink(self, path):
        """
        Find the root of a set of symbolic links.

        path is the path of the symlink to read.

        This method returns the target of the link, or a Deferred that
        returns the same.
        """
        path = self._absPath(path)
        return self._runAsUser(os.readlink, path)

    def makeLink(self, linkPath, targetPath):
        """
        Create a symbolic link.

        linkPath is is the pathname of the symlink as a string
        targetPath is the path of the target of the link as a string.

        This method returns when the link is made, or a Deferred that
        returns the same.
        """
        linkPath = self._absPath(linkPath)
        targetPath = self._absPath(targetPath)
        return self._runAsUser(os.symlink, targetPath, linkPath)

    def realPath(self, path):
        """
        Convert any path to an absolute path.

        path is the path to convert as a string.

        This method returns the absolute path as a string, or a Deferred
        that returns the same.
        """
        return self._absPath(path)

class SFTPError(Exception):

    def __init__(self, errorCode, errorMessage, lang):
        Exception.__init__(self)
        self.code = errorCode
        self.message = errorMessage
        self.lang = lang

    def __str__(self):
        return 'SFTPError %s: %s' % (self.code, self.message)


def _lsLine(name, s):
    mode = s.st_mode
    perms = array.array('c', '-'*10)
    ft = stat.S_IFMT(mode)
    if stat.S_ISDIR(ft): perms[0] = 'd'
    elif stat.S_ISCHR(ft): perms[0] = 'c'
    elif stat.S_ISBLK(ft): perms[0] = 'b'
    elif stat.S_ISREG(ft): perms[0] = '-'
    elif stat.S_ISFIFO(ft): perms[0] = 'f'
    elif stat.S_ISLNK(ft): perms[0] = 'l'
    elif stat.S_ISSOCK(ft): perms[0] = 's'
    else: perms[0] = '!'
    # user
    if mode&stat.S_IRUSR:perms[1] = 'r'
    if mode&stat.S_IWUSR:perms[2] = 'w'
    if mode&stat.S_IXUSR:perms[3] = 'x'
    # group
    if mode&stat.S_IRGRP:perms[4] = 'r'
    if mode&stat.S_IWGRP:perms[5] = 'w'
    if mode&stat.S_IXGRP:perms[6] = 'x'
    # other
    if mode&stat.S_IROTH:perms[7] = 'r'
    if mode&stat.S_IWOTH:perms[8] = 'w'
    if mode&stat.S_IXOTH:perms[9] = 'w'
    # suid/sgid
    if mode&stat.S_ISUID:
        if perms[3] == 'x': perms[3] = 's'
        else: perms[3] = 'S'
    if mode&stat.S_ISGID:
        if perms[6] == 'x': perms[6] = 's'
        else: perms[6] = 'S'
    l = perms.tostring()
    l += str(s.st_nlink).rjust(5) + ' '
    un = str(s.st_uid)
    l += un.ljust(9)
    gr = str(s.st_gid)
    l += gr.ljust(9)
    sz = str(s.st_size)
    l += sz.rjust(8)
    l += ' '
    sixmo = 60 * 60 * 24 * 7 * 26
    if s.st_mtime + sixmo < time.time(): # last endited more than 6mo ago
        l += time.strftime("%b %2d  %Y ", time.localtime(s.st_mtime))
    else:
        l += time.strftime("%b %2d %H:%S ", time.localtime(s.st_mtime))
    l += name
    return l

FXP_INIT            =   1
FXP_VERSION         =   2
FXP_OPEN            =   3
FXP_CLOSE           =   4
FXP_READ            =   5
FXP_WRITE           =   6
FXP_LSTAT           =   7
FXP_FSTAT           =   8
FXP_SETSTAT         =   9
FXP_FSETSTAT        =  10
FXP_OPENDIR         =  11
FXP_READDIR         =  12
FXP_REMOVE          =  13
FXP_MKDIR           =  14
FXP_RMDIR           =  15
FXP_REALPATH        =  16
FXP_STAT            =  17
FXP_RENAME          =  18
FXP_READLINK        =  19
FXP_SYMLINK         =  20
FXP_STATUS          = 101
FXP_HANDLE          = 102
FXP_DATA            = 103
FXP_NAME            = 104
FXP_ATTRS           = 105
FXP_EXTENDED        = 200
FXP_EXTENDED_REPLY  = 201

FILEXFER_ATTR_SIZE        = 0x00000001
FILEXFER_ATTR_OWNERGROUP  = 0x00000002
FILEXFER_ATTR_PERMISSIONS = 0x00000004
FILEXFER_ATTR_ACMODTIME   = 0x00000009
FILEXFER_ATTR_EXTENDED    = 0x+80000000

FILEXFER_TYPE_REGULAR        = 1
FILEXFER_TYPE_DIRECTORY      = 2
FILEXFER_TYPE_SYMLINK        = 3
FILEXFER_TYPE_SPECIAL        = 4
FILEXFER_TYPE_UNKNOWN        = 5

FXF_READ          = 0x00000001
FXF_WRITE         = 0x00000002
FXF_APPEND        = 0x00000004
FXF_CREAT         = 0x00000008
FXF_TRUNC         = 0x00000010
FXF_EXCL          = 0x00000020
FXF_TEXT          = 0x00000040

FX_OK                          = 0
FX_EOF                         = 1
FX_NO_SUCH_FILE                = 2
FX_PERMISSION_DENIED           = 3
FX_FAILURE                     = 4
FX_BAD_MESSAGE                 = 5
FX_NO_CONNECTION               = 6
FX_CONNECTION_LOST             = 7
FX_OP_UNSUPPORTED              = 8

import filetransfer
packetTypes = {}
for name in dir(filetransfer):
    if name.startswith('FXP_'):
        value = getattr(filetransfer, name)
        packetTypes[value] = name[4:]
FileTransferBase.packetTypes = packetTypes

