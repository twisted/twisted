cimport tcp

ctypedef unsigned int size_t

cdef extern from "stdlib.h":
    void free(void *ptr)
    void* malloc(size_t size)
    void* memchr(void *s, int c, size_t n)
    void* memcpy(void* dest, void* src, size_t n)


cdef class SampleProtocol(tcp.CProtocol):
    """Count line size. Assumes lines smaller than 8192 bytes."""

    cdef char buf[100000]
    cdef char* readbuf # current place where unfinished lines start
    cdef int readlen # amount of data from readbuf
    cdef int counter

    def connectionMade(self):
        self.readbuf = self.buf
        self.readlen = 0
        self.counter = 0
        self.ctransport.setReadBuffer(self.buf, 100000)

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
