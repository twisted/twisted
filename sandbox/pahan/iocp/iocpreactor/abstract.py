from twisted.python import log
from twisted.persisted import styles
from twisted.internet import interfaces

from win32file import AllocateReadBuffer

class IoHandle(log.Logger, styles.Ephemeral):
    __implements__ = (interfaces.ITransport,)
    dataBuffers = [] # list of strings, first one is being sent

    def __init__(self, reactor=None):
        if not reactor:
            from twisted.internet import reactor
        self.reactor = reactor
        self.readbuf = AllocateReadBuffer(8192)

    def write(self, data):

    def do_1(self, ret, bytes):
        """write done"""

