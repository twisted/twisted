from twisted.python import log
from twisted.persisted import styles
from twisted.internet import interfaces

from win32file import AllocateReadBuffer

class IoHandle(log.Logger, styles.Ephemeral):
    __implements__ = (interfaces.ITransport,)
#    dataBuffer = None # TODO: pretty please refactor me to be a list and later to use scatter/gather IO
#    offset = 0

    def __init__(self, reactor=None):
        if not reactor:
            from twisted.internet import reactor
        self.reactor = reactor
        self.readbuf = AllocateReadBuffer(8192)

    def write(self, data):
        self.issueWrite(data)

    def do_1(self, ret, bytes):
        """write done"""
        pass

