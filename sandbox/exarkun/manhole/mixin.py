
from twisted.internet import reactor

class BufferingMixin:
    """Mixin which adds write buffering.
    """
    _delayedWriteCall = None
    bytes = None

    DELAY = 0.0

    def write(self, bytes):
        """Buffer some bytes to be written soon.

        Every call to this function delays the real write by C{self.DELAY}
        seconds.  When the delay expires, all collected bytes are written
        to the underlying transport using C{ITransport.writeSequence}.
        """
        if self._delayedWriteCall is None:
            self.bytes = []
            self._delayedWriteCall = reactor.callLater(self.DELAY, self.flush)
        else:
            self._delayedWriteCall.reset(self.DELAY)
        self.bytes.append(bytes)

    def flush(self):
        """Flush the buffer immediately.
        """
        self._delayedWriteCall = None
        self.transport.writeSequence(self.bytes)
        self.bytes = None
