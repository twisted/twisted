cimport tcp
ctypedef unsigned int size_t

cdef extern from "string.h":
    void* memchr(void *s, int c, size_t n)
    char* strncpy(char* dest, char* src, size_t n)
cdef extern from "stdlib.h":
    void free(void *ptr)


cdef class SampleProtocol(tcp.CProtocol):
    """Count line size. Assumes lines smaller than 8192 bytes."""
    
    cdef char buf[100000]
    cdef char* readbuf # current place where unfinished lines start
    cdef int readlen # amount of data from readbuf
    cdef int counter
    
    def connectionMade(self):
        cdef tcp._CMixin transport
        self.readbuf = self.buf
        self.readlen = 0
        self.counter = 0
        self.transport.setBuffer(self.buf, 100000)

    cdef void cdataReceived(self, char* buffer, int buflen):
        cdef char* line_end
        cdef char* line
        cdef int line_len
        self.readlen = self.readlen + buflen
        while 1:
            line_end = <char*>memchr(self.readbuf, c'\n', self.readlen)
            if line_end:
                line_len = line_end - self.readbuf + 1
                strncpy(line, self.readbuf, line_len)
                self.readbuf = self.readbuf + line_len
                self.readlen = self.readlen - line_len
                self.lineReceived(line, line_len)
            else:
                break
        if self.readbuf != self.buf and (self.buffer + 100000 - self.readbuf - self.readlen) < 8192:
            strncpy(self.buf, self.readbuf, self.readlen)
            self.readbuf = self.buf

    cdef void lineReceived(self, char* line, int size):
        self.counter = self.counter + 1
        free(line)
    
    def connectionLost(self, reason):
        print self.counter
