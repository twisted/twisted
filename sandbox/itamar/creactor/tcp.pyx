# Python imports
from twisted.internet.tcp import Connection
from twisted.internet import main

cdef extern from "unistd.h":
    ssize_t read(int fd, void* buf, size_t count)
cdef extern from "errno.h":
    int EWOULDBLOCK


# see tcp.pxd for attributes definition
cdef class CProtocol:
    """Count line size. Assumes lines smaller than 8192 bytes."""
        
    def makeConnection(self, transport):
        """Make a connection to a transport and a server.

        This sets the 'transport' attribute of this Protocol, and calls the
        connectionMade() callback.
        """
        self.transport = transport
        self.ctransport = transport
        self.connectionMade()

    cdef void cdataReceived(self, char* buffer, int buflen):
        """Override in subclasses."""
        
    cdef void cbufferFull(self):
        """Override in subclasses."""


cdef class Buffer:
    """Allow passing char*s into Python code."""

    cdef init(self, void (*deallocator)(void*), char* buffer, int buflen):
        self.dealloc = deallocator
        self.buffer = buffer
        self.buflen = buflen

    cdef __dealloc__(self):
        self.dealloc(self.buffer)

    cdef __getreadbuffer__(self, int segment, void **ptrptr):
        if (segment == 0):
            ptrptr[0] = self.buffer
            return self.buflen

    cdef __getsegcount__(self, int *lenp):
        if lenp != NULL:
            lenp[0] = self.buflen
        return 1


# see tcp.pxd for definition of the attributes
cdef public class _CMixin [object TwistedTransport, type TwistedTransportType]:

    def __init__(self):
        """Call after tcp.Connection.__init__ is called."""
        if isinstance(self.protocol, CProtocol):
            self.cprotocol = self.protocol
            self._c_socketfd = self.fileno()
        else:
            self.cprotocol = 0
            
    cdef void setReadBuffer(self, char* buffer, size_t buflen):
        self._c_buffer = buffer
        self._c_buflen = buflen

    cdef void cwrite(self, Buffer b):
        self.write(b)
    
    def doRead(self):
        """doRead for tcp.Connection that knows about cProtocol."""
        cdef int result
        if self.cprotocol:
            if self._c_buflen == 0:
                self.cprotocol.cbufferFull()
                return
            result = read(self._c_socketfd, self._c_buffer, self._c_buflen)
            if result == 0:
                return main.CONNECTION_DONE
            elif result > 0:
                self._c_buffer = self._c_buffer + result
                self._c_buflen = self._c_buflen - result
                self.cprotocol.cdataReceived(self._c_buffer - result, result)
            else:
                if result == EWOULDBLOCK:
                    return
                else:
                    return main.CONNECTION_LOST
        else:
            return Connection.doRead(self)


cdef public void tt_setReadBuffer(_CMixin transport, char* buffer, size_t buflen):
    transport.setReadBuffer(buffer, buflen)

cdef public void tt_write(_CMixin transport, void (*deallocator)(void*), char* buffer, size_t buflen):
    cdef Buffer b
    b = Buffer()
    b.init(deallocator, buffer, buflen)
    transport.cwrite(b)
