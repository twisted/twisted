from twisted.internet import defer
import os, errno, time

def createLock(lockedFile, retryCount = 10, retryTime = 5, usePID = 0):
    filename = lockedFile + ".lock"
    d = defer.Deferred()
    _tryCreateLock(d, filename, retryCount, 0, retryTime, usePID)
    return d

class DidNotGetLock(Exception): pass

class LockFile:

    def __init__(self, filename, writePID):
        from twisted.internet import reactor
        pid = os.getpid()
        t = (time.time()%1)*10
        host = os.uname()[1]
        uniq = ".lk%05d%x%s" % (pid, t, host)
        if writePID:
            data = str(os.getpid())
        else:
            data = ""
        open(uniq,'w').write(data)
        uniqStat = list(os.stat(uniq))
        del uniqStat[3]
        try:
            os.link(uniq, filename)
        except:
            pass
        fileStat = list(os.stat(filename))
        del fileStat[3]
        if fileStat != uniqStat:
            raise DidNotGetLock()
        self.filename = filename
        self._killLaterTouch = reactor.callLater(60, self._laterTouch)

    def _laterTouch(self):
        from twisted.internet import reactor
        self.touch()
        self._killLaterTouch = reactor.callLater(60, self._laterTouch)

    def touch(self):
        f = open(self.filename, 'w')
        f.seek(0)
        f.write(str(os.getpid()))
        f.close() # keep the lock fresh

    def remove(self):
        self._killLaterTouch.cancel()
        os.remove(self.filename)


def _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID):
    from twisted.internet import reactor
    if retryCount == retryCurrent:
        return d.errback(DidNotGetLock())
    if retryTime > 60: retryTime = 60
    try:
        l = LockFile(filename, usePID)
    except DidNotGetLock:
        s = os.stat(filename)
        if (time.time() - s.st_atime) > 300: # older than 5 minutes
            os.remove(filename)
            return _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID)
        if usePID:
            try:
                pid = int(open(filename).read())
            except ValueError:
                return _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID)
            try:
                os.kill(pid, 0)
            except OSError, why:
                if why[0] == errno.ESRCH:
                    os.remove(filename)
                    return _tryCreateLock(d, filename, retryCount, retryCurrent, retryTime, usePID)
    else:
        return d.callback(l)
    reactor.callLater(retryTime, _tryCreateLock, d, filename, retryCount, retryCurrent+1, retryTime + 5, usePID)

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
