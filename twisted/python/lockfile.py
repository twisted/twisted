# -*- test-case-name: twisted.test.test_lockfile -*-
# Twisted, the Framework of Your Internet
# Copyright (C) 2004 Matthew W. Lefkowitz
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

"""Lock files.

Currently in a state of flux, API is unstable.
"""

from twisted.internet import defer
import os, errno, time

def createLock(lockedFile, schedule, retryCount = 10, retryTime = 5, usePID = 0):
    filename = lockedFile + ".lock"
    d = defer.Deferred()
    _tryCreateLock(d, filename, retryCount, 0, retryTime, usePID, schedule)
    return d

class DidNotGetLock(Exception): 
    def __repr__(self):
        return "DidNotGetLock()"

    __str__ = __repr__

class LockFile:

    def __init__(self, filename, writePID, schedule):
        pid = os.getpid()
        t = (time.time()%1)*10
        host = os.uname()[1]
        uniq = os.path.join(os.path.dirname(filename), 
                            ".lk%05d%x%s" % (pid, t, host))
        if writePID:
            data = str(os.getpid())
        else:
            data = "a"
        open(uniq,'w').write(data)
        uniqStat = list(os.stat(uniq))
        del uniqStat[3]
        try:
            os.link(uniq, filename)
        except:
            pass
        fileStat = list(os.stat(filename))
        del fileStat[3]
        os.remove(uniq)
        if fileStat != uniqStat:
            raise DidNotGetLock()
        self.filename = filename
        self.writePID = writePID
        self.schedule = schedule
        self._killLaterTouch = self.schedule(60, self._laterTouch)

    def _laterTouch(self):
        self.touch()
        self._killLaterTouch = self.schedule(60, self._laterTouch)

    def touch(self):
        f = open(self.filename, 'w')
        f.seek(0)
        if self.writePID:
            f.write(str(os.getpid()))
        else:
            f.write("a")
        f.close() # keep the lock fresh

    def remove(self):
        self._killLaterTouch.cancel()
        os.remove(self.filename)


def _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID, schedule):
    if retryTime > 60: retryTime = 60
    try:
        l = LockFile(filename, usePID, schedule)
    except DidNotGetLock:
        s = os.stat(filename)
        if (time.time() - s.st_atime) > 300: # older than 5 minutes
            os.remove(filename)
            return _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID, schedule)
        if usePID:
            try:
                pid = int(open(filename).read())
            except ValueError:
                os.remove(filename)
                return _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID, schedule)
            try:
                os.kill(pid, 0)
            except OSError, why:
                if why[0] == errno.ESRCH:
                    os.remove(filename)
                    return _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID, schedule)
    else:
        return d.callback(l)
    retryCurrent +=1 
    if retryCount == retryCurrent:
        return d.errback(DidNotGetLock())

    schedule(retryTime, _tryCreateLock, d, filename, retryCount, retryCurrent, retryTime + 5, usePID, schedule)

def checkLock(lockedFile, usePID=0):
    filename = lockedFile + ".lock"
    if not os.path.exists(filename):
        return 0
    s = os.stat(filename)
    if (time.time() - s.st_atime) > 300: # older than 5 minutes
        return 0
    if usePID:
        try:
            pid = int(open(filename).read())
        except ValueError:
            return 0
        try:
            os.kill(pid, 0)
        except OSError, why:
            if why[0] == errno.ESRCH: # dead pid
                return 0
    return 1

__all__ = ["createLock", "checkLock"]
