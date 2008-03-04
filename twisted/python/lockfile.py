# -*- test-case-name: twisted.test.test_lockfile -*-
# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.


"""
Lock files.
"""

__metaclass__ = type

import errno, os

from time import time as _uniquefloat

def unique():
    return str(long(_uniquefloat() * 1000))

try:
    from os import symlink
    from os import readlink
    from os import remove as rmlink
    from os import rename as mvlink
except:
    # XXX Implement an atomic thingamajig for win32
    import shutil
    def symlink(value, filename):
        newlinkname = filename+"."+unique()+'.newlink'
        newvalname = os.path.join(newlinkname,"symlink")
        os.mkdir(newlinkname)
        f = open(newvalname,'wb')
        f.write(value)
        f.flush()
        f.close()
        try:
            os.rename(newlinkname, filename)
        except:
            os.remove(newvalname)
            os.rmdir(newlinkname)
            raise

    def readlink(filename):
        return open(os.path.join(filename,'symlink'),'rb').read()

    def rmlink(filename):
        shutil.rmtree(filename)

    def mvlink(src, dest):
        try:
            shutil.rmtree(dest)
        except:
            pass
        os.rename(src,dest)


class FilesystemLock:
    """A mutex.

    This relies on the filesystem property that creating
    a symlink is an atomic operation and that it will
    fail if the symlink already exists.  Deleting the
    symlink will release the lock.

    @ivar name: The name of the file associated with this lock.
    @ivar clean: Indicates whether this lock was released cleanly by its
    last owner.  Only meaningful after C{lock} has been called and returns
    True.
    """

    clean = None
    locked = False

    def __init__(self, name):
        self.name = name

    def lock(self):
        """Acquire this lock.

        @rtype: C{bool}
        @return: True if the lock is acquired, false otherwise.

        @raise: Any exception os.symlink() may raise, other than
        EEXIST.
        """
        try:
            pid = readlink(self.name)
        except (OSError, IOError), e:
            if e.errno != errno.ENOENT:
                raise
            self.clean = True
        else:
            if not hasattr(os, 'kill'):
                return False
            try:
                os.kill(int(pid), 0)
            except (OSError, IOError), e:
                if e.errno != errno.ESRCH:
                    raise
                rmlink(self.name)
                self.clean = False
            else:
                return False

        symlink(str(os.getpid()), self.name)
        self.locked = True
        return True

    def unlock(self):
        """Release this lock.

        This deletes the directory with the given name.

        @raise: Any exception os.readlink() may raise, or
        ValueError if the lock is not owned by this process.
        """
        pid = readlink(self.name)
        if int(pid) != os.getpid():
            raise ValueError("Lock %r not owned by this process" % (self.name,))
        rmlink(self.name)
        self.locked = False


def isLocked(name):
    """Determine if the lock of the given name is held or not.

    @type name: C{str}
    @param name: The filesystem path to the lock to test

    @rtype: C{bool}
    @return: True if the lock is held, False otherwise.
    """
    l = FilesystemLock(name)
    result = None
    try:
        result = l.lock()
    finally:
        if result:
            l.unlock()
    return not result


__all__ = ['FilesystemLock', 'isLocked']

