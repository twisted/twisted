from twisted.internet import protocol

from cStringIO import StringIO
from struct import pack, unpack

class ImplicitStateProtocol(protocol.Protocol):
    implicit_state = (self._blowUp, 0)
    buffer = None

    def __init__(self):
        self.buffer = StringIO()

    def _blowUp(self, data):
        """A kind reminder"""
        raise NotImplementedError, "please override the implicit_state tuple attribute in the subclass"

    def dataReceived(self, data):
        left = self.next_len - self.buffer.tell()
        if left > len(data):
            self.buffer.write(data)
            return
        self.buffer.write(data[:left])
        data = data[left:]
        message = self.buffer.getvalue()
        self.buffer.reset()
        self.buffer.truncate()
        next = self.next_func(message)
        if next is None:
            self.transport.loseConnection()
            return
        self.next_len, self.next_func = next

