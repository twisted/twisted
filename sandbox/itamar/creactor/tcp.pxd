# useful general C stuff
ctypedef int ssize_t
ctypedef unsigned int size_t

# forward declaration
cdef class CProtocol

cdef class _CMixin:
    cdef char* _c_buffer
    cdef size_t _c_buflen
    cdef CProtocol cprotocol
    cdef int _c_socketfd

    cdef void setReadBuffer(self, char* buffer, size_t buflen)


cdef class CProtocol:
    cdef _CMixin ctransport
    cdef object transport # for ref counting

    cdef void cdataReceived(self, char* buffer, int buflen)
    cdef void cbufferFull(self)
