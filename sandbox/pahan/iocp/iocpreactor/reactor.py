# TODO:
# allow removal from handlers list

from twisted.internet.default import PosixReactorBase
from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorThreads, IReactorPluggableResolver
from twisted.python import log, threadable
from twisted.persisted import styles
from win32file import CreateIoCompletionPort, INVALID_HANDLE_VALUE, GetQueuedCompletionStatus, PostQueuedCompletionStatus
from win32event import INFINITE
from pywintypes import OVERLAPPED

# XXX: perhaps need to inherit from ReactorBase and incur some code duplication
class IOCPProactor(PosixReactorBase):
    __implements__ = (IReactorCore, IReactorTime)
    handles = None
    iocp = None

    def __init__(self):
        PosixReactorBase.__init__(self)
        self.handles = {}
        self.iocp = CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 1)

    def installWaker(self):
        if not self.waker:
            self.waker = IOCPWaker()

    def registerHandle(self, handle, handler):
        CreateIoCompletionPort(int(handle), iocp, handle, 1)
        self.handles[int(handle)] = handler

    def doIteration(self, timeout):
        if timeout is None:
            timeout = INFINITE
        else:
            timeout = int(timeout * 1000)
        (ret, bytes, key, ov) = GetQueuedCompletionStatus(iocp, timeout)
        if int(key) not in handles:
            raise ValueError("unexpected completion key %s" % (key,)) # what's the right thing to do here?
        print "IOCPReactor got event", ret, bytes, key, ov, ov.object
        m = o.getattr(str(ov.object))
        print "... calling", m, "to handle"
        m(ret, bytes)

class IOCPWaker(log.Logger, styles.Ephemeral):
    def wakeUp(self):
        ov = OVERLAPPED()
        ov.object = self
        PostQueuedCompletionStatus(iocp, 0, 0, ov)

    def do_unknown(self, ret, bytes, ov):
        pass

def install():
    threadable.init(1)
    i = IOCPProactor()
    from twisted.internet import main
    main.installReactor(i)

if __name__ == "__main__":
    IOCPReactor()

