
from twisted.internet import reactor

class BufferingMixin:
    _delayedWriteCall = None
    bytes = None

    DELAY = 0.0

    def write(self, bytes):
        if self._delayedWriteCall is None:
            self.bytes = []
            self._delayedWriteCall = reactor.callLater(self.DELAY, self.flush)
        else:
            self._delayedWriteCall.reset(self.DELAY)
        self.bytes.append(bytes)

    def flush(self):
        self._delayedWriteCall = None
        self.transport.writeSequence(self.bytes)
        self.bytes = None
