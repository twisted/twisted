from twisted.internet.default import PosixReactorBase
from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorThreads, IReactorPluggableResolver
from twisted.python import log
from twisted.persisted import styles
from win32file import CreateIoCompletionPort, INVALID_HANDLE_VALUE, GetQueuedCompletionStatus, PostQueuedCompletionStatus
from win32event import INFINITE
from pywintypes import OVERLAPPED

iocp = CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 0) # make concurrency value tunable if this thing proves to be useful
completables = {}

# XXX: perhaps need to inherit from ReactorBase and incur some code duplication
class IOCPReactor(PosixReactorBase):
    __implements__ = (IReactorCore, IReactorTime, IReactorThreads, IReactorPluggableResolver)

    def installWaker(self):
        if not self.waker:
            self.waker = IOCPWaker()

    def doIteration(self, timeout):
        if timeout is None:
            timeout = INFINITE
        else:
            timeout = int(timeout * 1000)
        (ret, bytes, key, ov) = GetQueuedCompletionStatus(iocp, timeout)
        o = ov.object
        m = o.getattr("do_%" % (key,), o.do_unknown)
        m(ret, bytes, ov)

class IOCPWaker(log.Logger, styles.Ephemeral):
    def wakeUp(self):
        ov = OVERLAPPED()
        ov.object = self
        PostQueuedCompletionStatus(iocp, 0, 0, ov)

    def do_unknown(self, ret, bytes, ov):
        pass

def install():
    i = IOCPReactor()
    from twisted.internet import main
    main.installReactor(i)

if __name__ == "__main__":
    IOCPReactor()

