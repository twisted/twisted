# Python imports
from twisted.internet.tcp import Connection
from twisted.internet import main

# C declarations
ctypedef int ssize_t
ctypedef unsigned int size_t

cdef extern from "unistd.h":
    ssize_t read(int fd, void* buf, size_t count)
cdef extern from "errno.h":
    int EWOULDBLOCK

cdef extern from "stdlib.h":
    void free(void *ptr)
    void* malloc(size_t size)
    void* memchr(void *s, int c, size_t n)
    void* memcpy(void* dest, void* src, size_t n)

# forward declaration
cdef class _CMixin


cdef class CProtocol:
    """Count line size. Assumes lines smaller than 8192 bytes."""
    
    cdef char buf[100000]
    cdef char* readbuf # current place where unfinished lines start
    cdef int readlen # amount of data from readbuf
    cdef int counter
    cdef _CMixin ctransport
    cdef object transport # for ref counting
    
    def makeConnection(self, transport):
        """Make a connection to a transport and a server.

        This sets the 'transport' attribute of this Protocol, and calls the
        connectionMade() callback.
        """
        self.transport = transport
        self.ctransport = transport
        self.connectionMade()

    def connectionMade(self):
        cdef _CMixin transport
        self.readbuf = self.buf
        self.readlen = 0
        self.counter = 0
        self.ctransport.setBuffer(self.buf, 100000)

    cdef void cbufferFull(self):
        print "WTF buffer full?"
        self.transport.loseConnection()
    
    cdef void cdataReceived(self, char* buffer, int buflen):
        cdef char* line_end
        cdef char* line
        cdef int line_len
        self.readlen = self.readlen + buflen
        while 1:
            line_end = <char*>memchr(self.readbuf, c'\n', self.readlen)
            if line_end:
                line_len = line_end - self.readbuf + 1
                line = <char*>malloc(line_len)
                memcpy(line, self.readbuf, line_len)
                self.readbuf = self.readbuf + line_len
                self.readlen = self.readlen - line_len
                self.lineReceived(line, line_len)
            else:
                break
        if (self.buf + 100000 - self.readbuf - self.readlen) < 8192:
            memcpy(self.buf, self.readbuf, self.readlen)
            self.readbuf = self.buf 
            self.ctransport.setBuffer(self.buf + self.readlen, 100000 - self.readlen)
    
    cdef void lineReceived(self, char* line, int size):
        self.counter = self.counter + 1
        free(line)
    
    def connectionLost(self, reason):
        print self.counter


cdef class _CMixin:

    cdef char* _c_buffer
    cdef size_t _c_buflen

    cdef setBuffer(self, char* buffer, size_t buflen):
        self._c_buffer = buffer
        self._c_buflen = buflen
    
    def doRead(self):
        """doRead for tcp.Connection that knows about cProtocol."""
        cdef int result
        cdef CProtocol protocol
        if isinstance(self.protocol, CProtocol): # XXX speed this up!
            protocol = self.protocol
            if self._c_buflen == 0:
                protocol.cbufferFull()
                return
            result = read(self.fileno(), self._c_buffer, self._c_buflen)
            if result == 0:
                return main.CONNECTION_DONE
            elif result > 0:
                self._c_buffer = self._c_buffer + result
                self._c_buflen = self._c_buflen - result
                protocol.cdataReceived(self._c_buffer - result, result)
            else:
                if result == EWOULDBLOCK:
                    return
                else:
                    return main.CONNECTION_LOST
        else:
            return Connection.doRead(self)
